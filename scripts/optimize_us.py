"""Full greedy optimizer on the US save with a 'play properly' welfare objective.

Restores balance>=0 then maximizes X, and prints the recommended policy SET (net changes vs the start)
to compare head-to-head with expert play (Pravus).
"""

from __future__ import annotations

from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import make_objective, greedy_optimize
from d3solver.savegame import load_savegame
from d3solver.scenario import anchor_equilibrium, from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}


def main() -> None:
    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    settings0 = {n: d["val"] for n, d in save.policies.items()}
    seed_state = dict(save.sim_values)
    seed_state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})
    seed_active = {n: bool(d["active"]) for n, d in save.situations.items()}
    scen = from_savegame(save)          # economy at its long-run average (notes/scope.md)
    exo = scen.exogenous
    ab = anchored_from_save(save, 1191.0, 1288.0,
                               model=model, anchor_state=anchor_equilibrium(model, scen))
    csv = calibrate(model, settings0, dict(save.sim_values), 1191.0, 1288.0)
    objective = make_objective(WEIGHTS)

    res = greedy_optimize(model, settings0, exo, objective, ab, csv.cost_k, csv.income_k,
                          init_values=seed_state, init_active=seed_active, freeze_active=True,
                          step=0.15, max_moves=40)

    print(f"moves applied: {len(res['history'])}")
    print(f"balance:  start -$97Bn  ->  ${res['balance']:.0f}Bn")
    print(f"objective X: {objective({n: seed_state.get(n, 0.0) for n in WEIGHTS}):.3f} -> {res['obj']:.3f}\n")

    changes = []
    for n, s0 in settings0.items():
        s1 = res["settings"][n]
        if abs(s1 - s0) > 1e-6:
            changes.append((n, s0, s1, s1 - s0))
    changes.sort(key=lambda c: abs(c[3]), reverse=True)
    print("RECOMMENDED POLICY SET (net change from start):")
    for n, s0, s1, d in changes:
        arrow = "RAISE" if d > 0 else "CUT  "
        print(f"  {arrow} {n:24s} {s0:.2f} -> {s1:.2f}  ({d:+.2f})")


if __name__ == "__main__":
    main()
