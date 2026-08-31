"""Global MILP solve on the US start, with every proposal re-scored by the exact Layer-1 solver.

This is the propose-high / verify-low loop the README describes, run twice over:

* **inside** each MILP, the situation binaries let the solver pick a *basin* rather than inherit one,
  which is the search the SLP cannot do (it freezes the situation set by construction); and
* **around** the MILP, the budget is re-linearised wherever the exact solver actually lands, because
  policy costs are multiplied by endogenous factors -- dominantly GDP -- so a budget linearised at the
  start state stops being true the moment the proposal moves the economy.

Every number reported as a result is the exact solver's. The MILP's own objective is shown only as the
optimistic proposal it is, next to the exact value, so the cost of the linearisation stays visible.

Usage:  python scripts/milp_us.py [--rounds 5] [--intervals 8] [--time-limit 300] [--freeze] [--msg]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.milp import refine_milp
from d3solver.optimize import evaluate, make_objective
from d3solver.savegame import load_savegame
from d3solver.scenario import from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
           "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}
INCOME_TARGET, EXPENDITURE_TARGET = 1191.0, 1288.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5, help="budget re-linearisation rounds")
    ap.add_argument("--intervals", type=int, default=8, help="PWL segments per nonlinear source")
    ap.add_argument("--time-limit", type=float, default=300.0, help="seconds per MILP solve")
    ap.add_argument("--gap", type=float, default=0.01, help="relative MIP gap to stop at")
    ap.add_argument("--freeze", action="store_true",
                    help="pin situations to the save's set (reproduces the SLP's frozen basin)")
    ap.add_argument("--msg", action="store_true", help="show CBC output")
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    cur = {n: d["val"] for n, d in save.policies.items()}
    ref_state = dict(save.sim_values)
    ref_state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})
    ref_active = {n: bool(d["active"]) for n, d in save.situations.items()}
    scen = from_savegame(save)          # economy at its long-run average (notes/scope.md)
    exo = scen.exogenous
    ab = anchored_from_save(save, INCOME_TARGET, EXPENDITURE_TARGET)
    csv = calibrate(model, cur, dict(save.sim_values), INCOME_TARGET, EXPENDITURE_TARGET)
    obj = make_objective(WEIGHTS)

    base_obj, base_bal, base_eq = evaluate(model, cur, exo, obj, ab, csv.cost_k, csv.income_k,
                                           ref_state, ref_active, True)
    base_on = {n for n, a in base_eq.active.items() if a}
    print(f"STATUS QUO (Layer 1):  X={base_obj:+.3f}  balance=${base_bal:+.0f}Bn  "
          f"{len(base_on)} situations active\n")

    print(f"MILP refinement (rounds={args.rounds}, intervals={args.intervals}, "
          f"situations={'FROZEN' if args.freeze else 'FREE -- the basin is a decision variable'})")
    res = refine_milp(
        model, exo, WEIGHTS, ab, csv.cost_k, csv.income_k,
        ref_state=ref_state, ref_active=ref_active,
        rounds=args.rounds, balance_min=0.0, freeze_active=args.freeze,
        intervals=args.intervals, time_limit=args.time_limit, gap_rel=args.gap,
        msg=1 if args.msg else 0,
    )
    for i, r in enumerate(res.rounds):
        print(r.line(i))

    sol = res.last
    print(f"\nmodel size: {sol.n_grids} PWL grids / {sol.n_binaries} binaries; "
          f"max PWL error {sol.max_pwl_error:.2e} ({sol.worst_pwl_formula})")
    if sol.problems:
        seen: dict[str, int] = {}
        for _, what, _why in sol.problems:
            seen[what] = seen.get(what, 0) + 1
        print(f"problems by kind: {seen}")

    verdict = "FEASIBLE" if res.feasible else "NO FEASIBLE ROUND (best-effort shown)"
    print(f"\nBEST ROUND, scored by Layer 1 -- {verdict}")
    print(f"  X       {base_obj:+.3f}  ->  {res.objective:+.3f}")
    print(f"  balance ${base_bal:+.0f}Bn  ->  ${res.balance:+.0f}Bn")

    eq = res.equilibrium
    exact_on = {n for n, a in eq.active.items() if a}
    print(f"\nBASIN (situations active):")
    print(f"  status quo : {len(base_on)}  {sorted(base_on)}")
    print(f"  optimum    : {len(exact_on)}  {sorted(exact_on)}")
    escaped, entered = sorted(base_on - exact_on), sorted(exact_on - base_on)
    if escaped:
        print(f"  ESCAPED    : {escaped}")
    if entered:
        print(f"  ENTERED    : {entered}")

    changes = [(n, cur.get(n, 0.0), res.settings[n], res.settings[n] - cur.get(n, 0.0))
               for n in res.settings if abs(res.settings[n] - cur.get(n, 0.0)) > 1e-3]
    changes.sort(key=lambda c: abs(c[3]), reverse=True)
    print(f"\nRECOMMENDED POLICY SET ({len(changes)} changes; top 20 by magnitude):")
    for n, s0, s1, d in changes[:20]:
        print(f"  {'RAISE' if d > 0 else 'CUT  '} {n:26s} {s0:.2f} -> {s1:.2f}  ({d:+.2f})")


if __name__ == "__main__":
    main()
