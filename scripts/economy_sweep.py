"""Sweep the world-economy cycle — does the savings buffer actually cover the busts?

`notes/scope.md` optimizes the **average-economy** equilibrium and enforces `balance >= 0` there, on
the reasoning that the live game oscillates and surpluses banked in booms pay for deficits in busts.
That is an assumption with a testable consequence, and this script tests it: take a policy vector,
hold it fixed, and re-solve the equilibrium at each point of the economy's range.

A vector that clears `balance >= 0` at the average but goes deeply negative across most of the cycle
is only nominally solvent — the buffer premise needs the *integral* to be non-negative, not the
midpoint. The verdict below reports both.

Caveat, stated because it changes how to read the result: the sweep is **uniform over [0,1]**. The
game's actual cycle (`GLOBAL_ECONOMY_CYCLE_LENGTH_YEARS = 8`, `GLOBAL_ECONOMY_INTENSITY = 0.5` in
`data/simconfig.txt`) is not uniform in occupancy, so the mean here is a proxy for the true
time-average, not the thing itself. Grounding that shape is open work.

Usage:  python scripts/economy_sweep.py [--vector optimum|current] [--points 11]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import evaluate, make_objective, slp_optimize
from d3solver.savegame import load_savegame
from d3solver.scenario import AVERAGE_ECONOMY, from_savegame, save_economy

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
           "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vector", choices=("optimum", "current"), default="optimum",
                    help="sweep the SLP optimum found at the average economy, or the save's own set")
    ap.add_argument("--points", type=int, default=11)
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)                      # average economy, per scope.md
    for note in scen.notes:
        print(f"note: {note}")
    print(f"save was played at economy={save_economy(save):.4f}; "
          f"this scenario pins it at {scen.economy:.4f}\n")

    ab = anchored_from_save(save, 1191.0, 1288.0)
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective(WEIGHTS)

    if args.vector == "optimum":
        print("finding the optimum at the average economy (trust-region SLP, basin frozen) ...")
        res = slp_optimize(model, scen.policies, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                           init_values=scen.ref_state, init_active=scen.ref_active,
                           freeze_active=True)
        vector = res["settings"]
        print(f"  X={res['obj']:+.3f}  balance=${res['balance']:+.0f}Bn  feasible={res['feasible']}\n")
    else:
        vector = scen.policies
        print("sweeping the save's own policy set\n")

    print(f"{'economy':>8s} {'X':>8s} {'balance':>10s} {'GDP':>7s} {'#sits':>6s}")
    print("-" * 44)
    rows = []
    for i in range(args.points):
        e = i / (args.points - 1)
        s = scen.with_economy(e)
        o, b, eq = evaluate(model, vector, s.exogenous, obj, ab, csv.cost_k, csv.income_k,
                            s.ref_state, s.ref_active, True)
        rows.append((e, o, b))
        mark = "  <- average" if abs(e - AVERAGE_ECONOMY) < 1e-9 else ""
        print(f"{e:8.2f} {o:+8.3f} {b:+9.0f}B {eq.values['GDP']:7.3f} "
              f"{sum(eq.active.values()):6d}{mark}")

    bals = [b for _, _, b in rows]
    mean_bal = sum(bals) / len(bals)
    print("-" * 44)
    print(f"balance: min ${min(bals):+.0f}Bn  mean ${mean_bal:+.0f}Bn  max ${max(bals):+.0f}Bn")

    # How much of this vector's budget can respond to the economy at all?
    live = [n for n, v in vector.items() if v > 1e-9]
    anchored = [n for n in live if ab.val0.get(n, 0.0) > 1e-9]
    csv_est = [n for n in live if n not in anchored]
    span = max(bals) - min(bals)
    print(f"\nbudget composition of the swept vector: {len(anchored)} anchored, "
          f"{len(csv_est)} CSV-estimated (of {len(live)} enacted)")

    print("""
CAVEAT -- read the verdict through this. `AnchoredBudget.cost(name, setting)` takes no state
argument: for every policy enacted in the save, cost and income scale with the slider alone and are
**invariant to the economy by construction**. Only the CSV-estimated policies carry the GDP-driven
multipliers. So the balance response measured above comes from part of the budget, not all of it --
7 policies whose CSVs declare a GDP multiplier are anchored, and have that term discarded.""")

    if span < 1e-6:
        print(f"""
VERDICT: NOT MEASURABLE with the current budget model. Balance is flat at ${mean_bal:+.0f}Bn across the
whole cycle because every enacted policy here is anchored, and the anchored path is economy-blind.
This says nothing about the savings-buffer premise -- it says the budget model cannot express it.""")
    elif min(bals) >= 0:
        print(f"""
VERDICT: solvent at every sampled point (min ${min(bals):+.0f}Bn), on the economy-sensitive
{len(csv_est)}-policy fraction of the budget. The buffer is not needed for that fraction.""")
    else:
        surplus = sum(b for b in bals if b > 0)
        deficit = -sum(b for b in bals if b < 0)
        first_ok = next((e for e, _, b in rows if b >= 0), None)
        holds = "HOLDS" if mean_bal >= 0 else "FAILS"
        print(f"""
VERDICT (partial -- see the caveat): on the economy-sensitive fraction, balance turns negative below
economy~{first_ok if first_ok is not None else float('nan'):.2f}, bottoming at ${min(bals):+.0f}Bn.
Summed surplus ${surplus:.0f}Bn vs summed deficit ${deficit:.0f}Bn, mean ${mean_bal:+.0f}Bn -- so on a
uniform sweep the savings-buffer premise {holds} for this vector.

Note the asymmetry's mechanism: GDP is clamped at its maximum, so once the economy is good enough to
pin it there the upside stops growing while the downside keeps costing. A buffer cannot be filled by
booms that are capped. Whether that survives a budget model with uniform economy sensitivity is open.""")


if __name__ == "__main__":
    main()
