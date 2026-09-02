"""Turn any computed policy vector into a checklist you can type into the Bench.

This is a **template generator, not a tool**. The point is that when a run produces something worth
reproducing — the ancapistan configuration, a frontier optimum, whatever comes next — you get a list
of exactly which sliders to move and to what, and nothing else. Everything not listed stays where the
starting point leaves it.

Sources it can turn into a recipe:

* a scenario id from ``web/scenarios.json`` (``us_start``, ``welfare``, ``growth``, ``equality``,
  ``safety``)
* a JSON file holding ``{"PolicyName": value, ...}``
* the built-ins below (``ancapistan``, ``free_laws``, ``private_only``) which are defined by *rule*
  rather than by a stored vector, so they stay correct if the game data changes

Output is Markdown by default (paste it anywhere) or JSON for the Atlas page.

Usage:
  python scripts/export_recipe.py --list
  python scripts/export_recipe.py ancapistan
  python scripts/export_recipe.py welfare --format json -o web/recipes.json --append
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import _cost, _income, evaluate, make_objective
from d3solver.savegame import load_savegame
from d3solver.scenario import anchor_equilibrium, from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
SHOW = ["GDP", "Unemployment", "PovertyRate", "CrimeRate", "Health", "Equality"]


def builtins(model):
    """Vectors defined by a rule, so they cannot go stale."""
    zero = {n: 0.0 for n in model.policies}
    free = [n for n, p in model.policies.items() if p.maxcost <= 0 and p.maxincome <= 0]
    priv = [n for n in ("HealthcareVouchers", "SchoolVouchers", "HealthTaxCredits",
                        "SchoolTaxCredits") if n in model.policies]
    return {
        "ancapistan": ("Ancapistan", "Every policy off. No revenue, so no spending: the 12 "
                       "cost-free laws are the entire policy space of a stateless state.", zero),
        "free_laws": ("Ancapistan + the free laws", "Still no taxation. Only the policies that "
                      "cost nothing and raise nothing are available.",
                      {**zero, **{n: 1.0 for n in free}}),
        "private_only": ("State-funded private provision only", "Blank slate plus the four voucher "
                         "and tax-credit policies that fund private provision, at full.",
                         {**zero, **{n: 1.0 for n in priv}}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", help="scenario id, built-in name, or a .json vector")
    ap.add_argument("--list", action="store_true", help="show what is available and exit")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("-o", "--out")
    ap.add_argument("--append", action="store_true", help="append to an existing json recipe list")
    ap.add_argument("--label"); ap.add_argument("--note")
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    bi = builtins(model)
    stored = {}
    sp = Path("web/scenarios.json")
    if sp.exists():
        stored = {x["id"]: x for x in json.loads(sp.read_text(encoding="utf-8"))}

    if args.list or not args.source:
        print("built-ins:  " + ", ".join(bi))
        print("scenarios:  " + (", ".join(stored) if stored else "(none — run export_scenarios.py)"))
        print("or pass a .json file of {\"PolicyName\": value}")
        return

    src = args.source
    if src in bi:
        label, note, vec = bi[src]
    elif src in stored:
        s = stored[src]
        label, note, vec = s["label"], s.get("note", ""), s["policies"]
    elif Path(src).exists():
        vec = json.loads(Path(src).read_text(encoding="utf-8"))
        label, note = args.label or Path(src).stem, args.note or ""
    else:
        raise SystemExit(f"unknown source {src!r} — try --list")
    label = args.label or label
    note = args.note or note

    ab = anchored_from_save(save, 1191.0, 1288.0,
                            model=model, anchor_state=anchor_equilibrium(model, scen))
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective({"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
                          "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0})
    full = dict(scen.policies); full.update(vec)
    o, b, eq = evaluate(model, full, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                        scen.ref_state, scen.ref_active, False)
    inc = sum(_income(n, v, ab, model, eq.values, csv.income_k) for n, v in full.items())
    cost = sum(_cost(n, v, ab, model, eq.values, csv.cost_k) for n, v in full.items())

    changes = [(n, scen.policies.get(n, 0.0), full[n]) for n in sorted(full)
               if abs(full[n] - scen.policies.get(n, 0.0)) > 0.005]
    changes.sort(key=lambda c: (model.policies[c[0]].department or "", model.policies[c[0]].guiname))

    if args.format == "json":
        rec = {"id": src, "label": label, "note": note,
               "objective": {"value": round(o, 4), "income": round(inc, 1),
                             "spend": round(cost, 1), "balance": round(inc - cost, 1)},
               "outcomes": {k: round(eq.values[k], 4) for k in SHOW},
               "policies": {n: round(v, 2) for n, v in full.items()}}
        out = Path(args.out) if args.out else None
        if out and args.append and out.exists():
            lst = json.loads(out.read_text(encoding="utf-8"))
            lst = [x for x in lst if x.get("id") != src] + [rec]
        else:
            lst = [rec]
        text = json.dumps(lst, separators=(",", ":"))
        (out.write_text(text, encoding="utf-8") if out else print(text))
        if out:
            print(f"wrote {out} ({len(lst)} recipes)")
        return

    lines = [f"# {label}", ""]
    if note:
        lines += [f"> {note}", ""]
    lines += [f"**Result** - X `{o:+.3f}` | income `${inc:.0f}Bn` | spending `${cost:.0f}Bn` | "
              f"balance `${inc-cost:+.0f}Bn`", "",
              "| outcome | value |", "|---|---|"]
    lines += [f"| {model.sim_values[k].guiname} | `{eq.values[k]:.3f}` |" for k in SHOW]
    lines += ["", f"## Set these {len(changes)} sliders in the Bench", "",
              "Reset to the US start first. Everything not listed stays where it is.", ""]
    dept = None
    for n, frm, to in changes:
        p = model.policies[n]
        d = p.department or "Other"
        if d != dept:
            lines += ["", f"### {d}", ""]
            dept = d
        lines.append(f"- [ ] **{p.guiname}** -> `{to:.2f}`  _(from {frm:.2f})_")
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8"); print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
