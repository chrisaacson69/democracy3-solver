"""Export the policy x outcome efficiency matrix, at equilibrium, with the direct/indirect split.

**Why equilibrium and not direct effects.** A table of each policy's own edges would be cheaper and
badly wrong. `HealthcareVouchers` has no edge to `Health` at all — it reaches it through
`PrivateHealthcare -> Health 0.3*(x^0.6)` — so a direct-effects table reports that health vouchers do
not affect health. Every interesting policy in this model works partly through the network.

So each policy is perturbed, the whole network is re-solved, and the change in *every* outcome is
recorded. One solve yields a policy's entire row, which is what makes the full 123 x 40 matrix cheap.

Three numbers per cell, because the difference between them is the point:

* ``total``    — the change at equilibrium. What actually happens.
* ``direct``   — the policy's own edge to that node, evaluated at the same point. Often zero.
* ``indirect`` — total minus direct. **This is the downstream effect**, and where it dominates you are
  looking at a policy that works by moving something else.

Cost is the change in budget balance, so a policy that improves an outcome *and* the balance is a free
win and is flagged rather than given a meaningless per-dollar ratio.

Usage:  python scripts/export_efficiency.py [-o web/efficiency.json] [--step 0.15]
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="web/efficiency.json")
    ap.add_argument("--step", type=float, default=0.15)
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    ab = anchored_from_save(save, 1191.0, 1288.0,
                            model=model, anchor_state=anchor_equilibrium(model, scen))
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective({})

    outcomes = [n for n, sv in model.sim_values.items()]

    def run(settings):
        _, _, eq = evaluate(model, settings, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                            scen.ref_state, scen.ref_active, False)
        inc = sum(_income(n, v, ab, model, eq.values, csv.income_k) for n, v in settings.items())
        cost = sum(_cost(n, v, ab, model, eq.values, csv.cost_k) for n, v in settings.items())
        return eq, inc - cost

    base_eq, base_bal = run(scen.policies)
    base_on = {n for n, v in base_eq.active.items() if v}
    print(f"baseline: balance ${base_bal:+.0f}Bn over {len(outcomes)} outcomes")

    rows = {}
    for i, (name, pol) in enumerate(model.policies.items(), 1):
        s = scen.policies.get(name, 0.0)
        new = min(1.0, s + args.step)
        direction = 1.0
        if abs(new - s) < 1e-9:                       # already at the top: probe downward
            new, direction = max(0.0, s - args.step), -1.0
        if abs(new - s) < 1e-9:
            continue
        st = dict(scen.policies); st[name] = new
        eq, bal = run(st)
        # A perturbation that flips a crisis produces a STEP, not a gradient. Reading such a cell as
        # a per-dollar efficiency is wrong: raising State Schools by 0.15 trips Teacher Shortage and
        # takes Education 0.920 -> 0.760, which is a threshold being crossed, not a rate of exchange.
        on = {n for n, v in eq.active.items() if v}
        flipped = sorted(model.situations[x].guiname or x for x in (on ^ base_on))

        # direct: this policy's own edge to each outcome, at the same x
        direct = {}
        for e in pol.effects:
            if e.target in model.sim_values:
                try:
                    direct[e.target] = direct.get(e.target, 0.0) + (
                        e.formula.evaluate(new, eq.values) - e.formula.evaluate(s, eq.values))
                except Exception:
                    pass

        cells = {}
        for k in outcomes:
            tot = direction * (eq.values[k] - base_eq.values[k])
            if abs(tot) < 1e-5 and k not in direct:
                continue                              # keep the payload to what actually moves
            d = direction * direct.get(k, 0.0)
            cells[k] = [round(tot, 5), round(d, 5)]
        rows[name] = {
            "gui": pol.guiname or name,
            "dept": pol.department or "Other",
            "from": round(s, 3), "to": round(new, 3), "dir": direction,
            "dbal": round(direction * (bal - base_bal), 2),
            "flipped": flipped,
            "cells": cells,
        }
        if i % 25 == 0:
            print(f"  {i}/{len(model.policies)}")

    payload = {
        "meta": {"step": args.step, "baseline": "US start, economy 0.5, crises free",
                 "base_balance": round(base_bal, 2),
                 "note": "total = equilibrium change; direct = this policy's own edge; "
                         "indirect = total - direct. `flipped` lists crises that switched "
                         "state under this perturbation -- those rows are steps, not gradients."},
        "outcomes": {k: {"gui": model.sim_values[k].guiname or k,
                         "emotion": model.sim_values[k].emotion,
                         "zone": model.sim_values[k].zone,
                         "base": round(base_eq.values[k], 4)} for k in outcomes},
        "policies": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB, {len(rows)} policies)")


if __name__ == "__main__":
    main()
