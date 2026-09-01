"""Sanity-check the rough budget model against the US save's screenshot totals.

Screenshot ground truth (US, turn 1): tax income $1191 Bn (92.5% of $1287 incl. $96.87 Bn borrowing),
expenditure $1288 Bn. After calibrating at this anchor, `balance` should reproduce the ~-$97 Bn deficit,
and the biggest cost lines should look like Military / State Pensions.
"""

from __future__ import annotations

from pathlib import Path

from d3solver import load_model
from d3solver.budget import calibrate, balance, raw_cost, raw_income
from d3solver.config import sim_dir
from d3solver.savegame import load_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
INCOME_TARGET = 1191.0       # $Bn tax income
EXPENDITURE_TARGET = 1288.0  # $Bn


def main() -> None:
    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    settings = {n: d["val"] for n, d in save.policies.items()}
    state = dict(save.sim_values)
    state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})

    UNIT = 1000.0  # save cost/income history is ~$M; /1000 -> $Bn
    cost_bn = {n: d["cost"] / UNIT for n, d in save.policies.items()}
    income_bn = {n: d["income"] / UNIT for n, d in save.policies.items()}
    tot_income = sum(income_bn.values())
    tot_cost = sum(cost_bn.values())
    print("[save-baselined actuals]")
    print(f"income=${tot_income:.1f}Bn  expenditure=${tot_cost:.1f}Bn  "
          f"balance=${tot_income - tot_cost:.1f}Bn  (game borrowing ~ -$96.9Bn)")
    top_c = sorted(cost_bn.items(), key=lambda x: x[1], reverse=True)[:6]
    top_i = sorted(income_bn.items(), key=lambda x: x[1], reverse=True)[:6]
    print("Top spend ($Bn):    ", ", ".join(f"{n} {c:.0f}" for n, c in top_c))
    print("Top revenue ($Bn):  ", ", ".join(f"{n} {c:.0f}" for n, c in top_i))
    print("  (game: Military 225, StatePensions 204, StateSchools 98, StateHealth 95, Space 78)")

    from d3solver.budget import anchored_from_save
    ab = anchored_from_save(save, INCOME_TARGET, EXPENDITURE_TARGET,
                            model=model, anchor_state=anchor_equilibrium(model, scen))
    bb = ab.balance(settings)
    print(f"\n[anchored + calibrated] income=${bb['income']:.1f}Bn  expenditure=${bb['expenditure']:.1f}Bn  "
          f"balance=${bb['balance']:.1f}Bn")
    # spot-check a Military cut, holding equilibrium fixed (partial view; full effect needs a re-solve)
    lowered = dict(settings); lowered["MilitarySpending"] = 0.376  # targ in the save
    print(f"  If Military 0.875->0.376: expenditure "
          f"${ab.balance(lowered)['expenditure']:.1f}Bn (frees ~${bb['expenditure']-ab.balance(lowered)['expenditure']:.0f}Bn)")


if __name__ == "__main__":
    main()
