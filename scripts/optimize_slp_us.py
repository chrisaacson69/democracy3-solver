"""Trust-region SLP on the US save (welfare objective) — the principled *local* constrained optimizer.

Prints the trust-region trace plus the recommended policy set. Read `rho` as the honesty check on each
step: it is the ratio of the merit gain actually achieved to the one the linear model promised, so a
low `rho` means the linearization was lying there and the step is rejected and the region shrunk. For
the *global* counterpart — which also chooses which situations are active, rather than freezing them —
see `scripts/milp_us.py`.
"""

from __future__ import annotations

from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import make_objective, slp_optimize
from d3solver.savegame import load_savegame
from d3solver.scenario import from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
# Welfare basket + GDP (GDP creates the tradeoff that stops trivial over-taxation)
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
           "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}


def main() -> None:
    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    cur = {n: d["val"] for n, d in save.policies.items()}
    seed_state = dict(save.sim_values)
    seed_state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})
    seed_active = {n: bool(d["active"]) for n, d in save.situations.items()}
    scen = from_savegame(save)          # economy at its long-run average (notes/scope.md)
    exo = scen.exogenous
    ab = anchored_from_save(save, 1191.0, 1288.0)
    csv = calibrate(model, cur, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective(WEIGHTS)

    res = slp_optimize(model, cur, exo, obj, ab, csv.cost_k, csv.income_k,
                       init_values=seed_state, init_active=seed_active, freeze_active=True)

    print("SLP trust-region trace (rho = actual/predicted merit gain; a bad step is rejected):")
    for i, t in enumerate(res["trace"]):
        verdict = "accept" if t["accepted"] else "REJECT"
        print(f"  {i:2d}: X={t['obj']:+.3f}  bal=${t['balance']:+6.0f}Bn  merit={t['merit']:+.3f}  "
              f"rho={t['rho']:+7.2f}  radius={t['radius']:.3f}  move={t['move']:.3f}  {verdict}")
    feas = "feasible" if res.get("feasible") else "INFEASIBLE"
    kept = sum(1 for t in res["trace"] if t["accepted"])
    print(f"\nfinal: X={res['obj']:.3f}  balance=${res['balance']:.0f}Bn  ({feas})  "
          f"iters={len(res['trace'])}  steps kept={kept}\n")

    changes = [(n, cur[n], res["settings"][n], res["settings"][n] - cur[n])
               for n in cur if abs(res["settings"][n] - cur[n]) > 1e-3]
    changes.sort(key=lambda c: abs(c[3]), reverse=True)
    print("RECOMMENDED POLICY SET (net change):")
    for n, s0, s1, d in changes[:18]:
        print(f"  {'RAISE' if d > 0 else 'CUT  '} {n:24s} {s0:.2f} -> {s1:.2f}  ({d:+.2f})")


if __name__ == "__main__":
    main()
