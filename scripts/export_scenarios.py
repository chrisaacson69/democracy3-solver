"""Precompute named policy vectors for the browser bench to load and compare.

The point of these is not that any one of them is *the* answer. It is that they are optimal for
**different objectives**, all under the same `balance >= 0` constraint and the same average economy —
so putting two of them side by side turns "is zero crime worth mass unemployment?" from an abstract
question into a concrete comparison of two states somebody could actually govern. That is the question
`notes/scope.md` says has no single answer, made touchable.

Each is solved by the trust-region SLP from the US start. Slow (a few minutes total), so it is a
separate step from the page build: the result is cached to JSON and `export_web_model.py` folds it in.

Usage:  python scripts/export_scenarios.py [-o scenarios.json]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import evaluate, make_objective, slp_optimize
from d3solver.savegame import load_savegame
from d3solver.scenario import from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")

# Deliberately incommensurable value systems. Each is a defensible thing to want; none dominates.
OBJECTIVES = [
    ("welfare", "Balanced welfare",
     "Health, equality and growth together, penalising poverty, unemployment and crime. The "
     "compromise basket — and the one that turns out to saturate.",
     {"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
      "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}),
    ("growth", "Growth above all",
     "Maximise GDP alone. Nothing else is valued, so whatever growth costs is simply not counted.",
     {"GDP": 1.0}),
    ("equality", "Equality and poverty",
     "Maximise equality and drive poverty down, indifferent to what it does to output.",
     {"Equality": 1.0, "PovertyRate": -1.0}),
    ("safety", "Zero crime at any price",
     "Minimise crime alone — the literal version of the question, so you can look at what it costs "
     "everywhere else.",
     {"CrimeRate": -1.0}),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="scenarios.json")
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    ab = anchored_from_save(save, 1191.0, 1288.0)
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)

    out = [{
        "id": "us_start",
        "label": "United States, as played",
        "note": "The save's own policy set — the country before anyone optimised anything.",
        "policies": scen.policies,
        "objective": None,
    }]

    for sid, label, note, weights in OBJECTIVES:
        t0 = time.time()
        obj = make_objective(weights)
        res = slp_optimize(model, scen.policies, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                           init_values=scen.ref_state, init_active=scen.ref_active,
                           freeze_active=True)
        o, b, _ = evaluate(model, res["settings"], scen.exogenous, obj, ab,
                           csv.cost_k, csv.income_k, scen.ref_state, scen.ref_active, True)
        out.append({
            "id": sid, "label": label, "note": note,
            "policies": {k: round(v, 4) for k, v in res["settings"].items()},
            "objective": {"weights": weights, "value": o, "balance": b,
                          "feasible": bool(res.get("feasible"))},
        })
        print(f"{sid:9s} X={o:+.3f} balance=${b:+.0f}Bn feasible={res.get('feasible')} "
              f"({time.time()-t0:.0f}s)")

    Path(args.out).write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out} ({len(out)} scenarios)")


if __name__ == "__main__":
    main()
