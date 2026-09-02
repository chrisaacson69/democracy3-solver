"""What is each crisis worth fixing, and what would fixing it cost?

The policy rankings answer "outcome per dollar". This is the same question asked of **crises**, which
turned out to matter more than expected: clearing crises first beats optimising welfare directly, on
both welfare and crisis count (`notes/findings.md`). So it is worth knowing which ones are actually
worth clearing — because some plainly cost more to fix than they return.

Two numbers per crisis, measured rather than assumed:

* **Worth** — force it inactive, hold everything else, re-solve, and take the change in the welfare
  basket. What the country gains from it simply being gone.
* **Cost** — how far its value has to fall to cross the stop trigger, divided by the best rate any
  single policy converts dollars into movement on that crisis. An estimate of the cheapest push.

`worth / cost` then ranks them the way `cost_effectiveness.py` ranks policies. A crisis that is free to
clear (some lever pays for itself) is flagged rather than given a ratio.

**What this is not.** The cost is a *linear extrapolation* from a small perturbation to a possibly
large distance, using the single best lever rather than the best portfolio, and clearing one crisis can
clear or cause others. It is a first-order ranking for deciding what to look at, not a plan. The
two-stage optimiser is what actually produces a plan.

Usage:  python scripts/crisis_value.py [--state us|welfare] [--step 0.15]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.loader import load_country
from d3solver.optimize import _cost, _income, evaluate, make_objective
from d3solver.savegame import load_savegame
from d3solver.scenario import anchor_equilibrium, from_savegame
from d3solver.solver import solve_equilibrium

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
COUNTRY = "usa"
W = {"Equality": 1.0, "Health": 1.0, "GDP": 1.0,
     "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", choices=("us", "welfare"), default="us")
    ap.add_argument("--step", type=float, default=0.15)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    model, overrides = load_country(sim_dir(), COUNTRY)
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    ab = anchored_from_save(save, 1191.0, 1288.0,
                            model=model, anchor_state=anchor_equilibrium(model, scen))
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective(W)

    base_vec = dict(scen.policies)
    if args.state == "welfare":
        sp = Path("web/scenarios.json")
        if sp.exists():
            for r in json.loads(sp.read_text(encoding="utf-8")):
                if r["id"] == "welfare":
                    base_vec.update(r["policies"])

    def run(vec):
        _, _, eq = evaluate(model, vec, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                            scen.ref_state, scen.ref_active, False)
        inc = sum(_income(n, v, ab, model, eq.values, csv.income_k) for n, v in vec.items())
        cost = sum(_cost(n, v, ab, model, eq.values, csv.cost_k) for n, v in vec.items())
        return eq, inc - cost

    eq0, bal0 = run(base_vec)
    x0 = sum(W[k] * eq0.values[k] for k in W)
    active = [n for n in model.situations if eq0.active[n]]
    print(f"state: {args.state}   X={x0:+.3f}   balance ${bal0:+.0f}Bn   "
          f"{len(active)} crises active ({sum(1 for n in active if not model.situations[n].positive)} harmful)")
    print(f"({len(overrides)} {COUNTRY} overrides applied)\n")

    # one pass over the policies: how does each move every crisis, and what does it cost?
    lever = {n: [] for n in model.situations}     # crisis -> [(d_value_per_$Bn, policy, d_bal)]
    for name, pol in model.policies.items():
        s = base_vec.get(name, 0.0)
        new = min(1.0, s + args.step)
        direction = 1.0
        if abs(new - s) < 1e-9:
            new, direction = max(0.0, s - args.step), -1.0
        if abs(new - s) < 1e-9:
            continue
        st = dict(base_vec); st[name] = new
        eq, bal = run(st)
        d_bal = direction * (bal - bal0)
        for c in model.situations:
            dv = direction * (eq.values[c] - eq0.values[c])
            if abs(dv) < 1e-5:
                continue
            # keep the per-POLICY-UNIT rate too: a lever that is cheap per dollar is useless
            # if it runs out of slider before it closes the gap.
            room = (1.0 - s) if direction > 0 else s
            lever[c].append((dv, name, d_bal, dv / args.step, room))

    rows = []
    for c in active:
        sit = model.situations[c]
        gap = eq0.values[c] - sit.stop_trigger          # how far it must fall to switch off
        if gap <= 0:
            continue
        # worth: force it off, hold the rest
        act = dict(eq0.active); act[c] = False
        eq = solve_equilibrium(model, base_vec, scen.exogenous, init_values=dict(eq0.values),
                               init_active=act, freeze_active=True)
        worth = sum(W[k] * eq.values[k] for k in W) - x0
        # cost: the best single lever that pushes it DOWN, priced per $Bn
        best_paid, best_free = None, None
        for dv, pname, d_bal, per_unit, room in lever[c]:
            if dv >= 0:
                continue                                # pushes it up
            need = gap / -per_unit                      # slider units required to close the gap
            if need > room + 1e-9:
                continue                                # this lever cannot reach, at any price
            if d_bal >= -1e-6:                          # closes it AND pays for itself
                if best_free is None or dv < best_free[0]:
                    best_free = (dv, pname, need)
            else:
                spend = (-d_bal) * (need / args.step)   # $Bn for the movement actually required
                if best_paid is None or spend < best_paid[0]:
                    best_paid = (spend, pname, need)
        if best_free:
            rows.append((float("inf"), c, worth, 0.0, best_free[1], gap, True))
        elif best_paid:
            est, pname, need = best_paid
            rows.append((worth / est if est > 1e-9 else float("inf"),
                         c, worth, est, pname, gap, False))
        else:
            rows.append((float("-inf"), c, worth, float("nan"), "(no lever found)", gap, False))

    rows.sort(key=lambda r: (-r[0] if r[0] != float("inf") else -1e18))
    print(f"{'crisis':24s} {'kind':8s} {'worth X':>8s} {'est cost':>9s} {'per $100Bn':>11s}  cheapest lever")
    print("-" * 96)
    for ratio, c, worth, est, pname, gap, free in rows[:args.top]:
        sit = model.situations[c]
        kind = "harmful" if not sit.positive else "GOOD"
        gui = model.policies[pname].guiname if pname in model.policies else pname
        if free:
            print(f"{sit.guiname[:24]:24s} {kind:8s} {worth:+8.4f} {'free':>9s} {'—':>11s}  {gui}")
        elif est != est:
            print(f"{sit.guiname[:24]:24s} {kind:8s} {worth:+8.4f} {'n/a':>9s} {'—':>11s}  {gui}")
        else:
            print(f"{sit.guiname[:24]:24s} {kind:8s} {worth:+8.4f} {est:8.0f}B {ratio*100:11.4f}  {gui}")
    print("\nworth = change in the welfare basket from it simply being gone.")
    print("est cost = the $Bn of the cheapest SINGLE lever that has enough slider range left")
    print("           to close the gap to the stop trigger. 'no lever' means no one policy can")
    print("           reach it alone, whatever the budget -- it needs a portfolio.")
    print("A negative 'worth' means the country is BETTER with it running — clearing it is a loss.")


if __name__ == "__main__":
    main()
