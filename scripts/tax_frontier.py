"""The tax dial: for each level of taxation, how good can the country be?

The question is *"what is the minimum tax needed to fund provision at an acceptable standard"* — but
asking for a single number turns out to be the wrong shape, and the first attempt at it failed
instructively. A greedy that only **cuts** spending cannot substitute: it can never discover "cut
pensions and add food stamps", because the second half raises spending and gets rejected before the
first half is allowed. And holding every outcome floor *exactly* at today's values leaves almost no
feasible set at all, since the status quo sits on the boundary — any tax rise pushes GDP below its
floor and any tax cut pushes the balance below zero.

So trace the whole frontier instead. Pin taxation at a level; let the optimiser spend what that raises
however it likes, subject to `balance >= 0`; record what the country ends up like. Read the minimum
acceptable tax off the curve against whatever bar you care about, rather than committing to one in
advance.

This is also the honest form of the question for the private-provision work: whatever the curve says
you can achieve at tax level *k* using the game's own policies is the bar an invented REA has to beat.

Usage:
  python scripts/tax_frontier.py [--points 7] [--mode scale|uniform]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import _cost, _income, evaluate, make_objective, slp_optimize
from d3solver.savegame import load_savegame
from d3solver.scenario import anchor_equilibrium, from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
           "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}
SHOW = ["GDP", "Unemployment", "PovertyRate", "CrimeRate", "Health", "Equality"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", type=int, default=7)
    ap.add_argument("--mode", choices=("scale", "uniform"), default="scale",
                    help="scale = multiply the 9 taxes the US levies; uniform = all 25 at one level")
    ap.add_argument("--lo", type=float, default=0.2)
    ap.add_argument("--hi", type=float, default=1.4)
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    ab = anchored_from_save(save, 1191.0, 1288.0,
                            model=model, anchor_state=anchor_equilibrium(model, scen))
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective(WEIGHTS)

    taxes = [n for n, p in model.policies.items() if p.maxincome > 0]
    on = [n for n in taxes if scen.policies.get(n, 0.0) > 1e-9]
    spenders = [n for n in model.policies if n not in taxes]

    def totals(settings, eq):
        inc = sum(_income(n, v, ab, model, eq.values, csv.income_k) for n, v in settings.items())
        cost = sum(_cost(n, v, ab, model, eq.values, csv.cost_k) for n, v in settings.items())
        return inc, cost

    o0, b0, eq0 = evaluate(model, scen.policies, scen.exogenous, obj, ab,
                           csv.cost_k, csv.income_k, scen.ref_state, scen.ref_active, False)
    i0, c0 = totals(scen.policies, eq0)
    print(f"US start (unoptimised): X={o0:+.3f}  income ${i0:.0f}Bn  spending ${c0:.0f}Bn  "
          f"balance ${i0-c0:+.0f}Bn")
    print(f"  " + "  ".join(f"{model.sim_values[k].guiname}={eq0.values[k]:.3f}" for k in SHOW))
    print(f"\nAt each tax level the {len(spenders)} non-tax policies are re-optimised for the welfare"
          f" basket\nsubject to balance >= 0. Taxes are held; only spending moves.\n")

    hdr = f"{'tax':>6s} {'income':>8s} {'spend':>8s} {'bal':>7s} {'X':>7s}  " + \
          "  ".join(f"{model.sim_values[k].guiname[:9]:>9s}" for k in SHOW)
    print(hdr); print("-" * len(hdr), flush=True)

    for i in range(args.points):
        k = args.lo + (args.hi - args.lo) * i / max(1, args.points - 1)
        p0 = dict(scen.policies)
        if args.mode == "scale":
            for n in on:
                p0[n] = min(1.0, scen.policies[n] * k)
        else:
            for n in taxes:
                p0[n] = min(1.0, k)
        # Multi-start, because a single start is demonstrably unreliable here: the first pass of this
        # frontier produced two rows that both dipped below their neighbours AND missed the balance
        # constraint. A monotone curve should not have holes in it, and those holes were the local
        # optimizer failing, not the world. At tax 1.00 the three starts land on X = +1.913, +1.909
        # and +0.047 — the last is a valid local optimum and a useless answer.
        best = None
        for st0 in (p0,
                    {**p0, **{n: 0.0 for n in spenders}},
                    {**p0, **{n: 1.0 for n in spenders}}):
            r = slp_optimize(model, st0, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                             init_values=scen.ref_state, init_active=scen.ref_active,
                             freeze_active=False, policies=spenders,
                             iters=80, delta=0.35, delta_min=0.001)
            oo, bb, _ = evaluate(model, r["settings"], scen.exogenous, obj, ab,
                                 csv.cost_k, csv.income_k, scen.ref_state, scen.ref_active, False)
            if bb >= -0.5 and (best is None or oo > best[0]):
                best = (oo, r)
        res = best[1] if best else r
        st = res["settings"]
        o, b, eq = evaluate(model, st, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                            scen.ref_state, scen.ref_active, False)
        inc, cost = totals(st, eq)
        feas = "" if (inc - cost) >= -0.5 else "  INFEASIBLE"   # tolerance, not 1e-6
        print(f"{k:6.2f} {inc:7.0f}B {cost:7.0f}B {inc-cost:+6.0f}B {o:+7.3f}  "
              + "  ".join(f"{eq.values[key]:9.3f}" for key in SHOW) + feas, flush=True)

    print("\nRead the minimum acceptable tax off the column you care about. Rows NOT marked")
    print("INFEASIBLE balance their budget; the rest could not be funded at that tax level.")


if __name__ == "__main__":
    main()
