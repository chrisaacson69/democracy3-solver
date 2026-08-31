"""First efficient-frontier pass on the US save with a Pravus-style welfare objective.

Objective X (pluggable weights): high Equality & Health, low Poverty, Unemployment, Crime.
We warm-start from the save (current basin) and report the best 'buys' (X per £) and 'cuts' (£ freed).
Validation target: should echo Pravus's economic core — cut Pensions/Military, fund welfare + growth.
"""

from __future__ import annotations

from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import make_objective, marginal_analysis, rank_moves
from d3solver.savegame import load_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}


def main() -> None:
    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    settings = {n: d["val"] for n, d in save.policies.items()}
    seed_state = dict(save.sim_values)
    seed_state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})
    seed_active = {n: bool(d["active"]) for n, d in save.situations.items()}
    exo = {
        "_global_socialism": save.globals.get("socialism", 0.5),
        "_global_liberalism": save.globals.get("liberalism", 0.5),
        "_globaleconomy_": save.globals.get("globaleconomy_pos", 0.5),
        "_year": save.globals.get("globaleconomy_years", 0.0),
    }

    ab = anchored_from_save(save, income_target=1191.0, expenditure_target=1288.0)
    state_for_csv = dict(save.sim_values)
    csv = calibrate(model, settings, state_for_csv, 1191.0, 1288.0)  # CSV scales for inactive policies

    objective = make_objective(WEIGHTS)
    base_obj, base_bal, rows = marginal_analysis(
        model, settings, exo, objective, ab, csv.cost_k, csv.income_k,
        step=0.1, init_values=seed_state, init_active=seed_active, freeze_active=True,
    )
    free_wins, paid_buys, savings = rank_moves(rows)

    print("objective X = +Equality +Health -Poverty -Unemployment -Crime")
    print(f"base X = {base_obj:.3f}   base balance = ${base_bal:.0f}Bn  (deficit)\n")
    print("FREE WINS (improve X AND the budget):")
    for r in free_wins[:8]:
        print(f"  {r['policy']:22s}{r['dir']}  dX={r['d_obj']:+.4f}  d$={r['d_bal']:+6.1f}Bn")
    print("\nPAID IMPROVEMENTS (improve X, cost money; best X per $Bn):")
    for r in paid_buys[:8]:
        print(f"  {r['policy']:22s}{r['dir']}  dX={r['d_obj']:+.4f}  d$={r['d_bal']:+6.1f}Bn  X/$={r['x_per_pound']:.4f}")
    print("\nSAVINGS WITH TRADEOFF ($ freed, X cost; most $ per X lost):")
    for r in savings[:8]:
        print(f"  {r['policy']:22s}{r['dir']}  dX={r['d_obj']:+.4f}  d$={r['d_bal']:+6.1f}Bn")


if __name__ == "__main__":
    main()
