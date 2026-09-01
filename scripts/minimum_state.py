"""How little tax is needed to hold outcomes at a chosen bar?

This is the question the whole cost-effectiveness line was building toward, and it is *not* "what tax
balances the current budget". It is:

    minimise taxation
    subject to  outcomes no worse than <bar>
                balance >= 0

Run in-model first, using only the game's own policies, before inventing any private-provision ones —
the answer tells you how much of the current state is load-bearing and how much is overpriced habit.
Whatever tax level survives this is the floor that private provision would have to beat.

Two stages, because they are separable:

1. **Shrink the state.** Greedily cut spending wherever it buys the least outcome, holding every floor.
   `notes/findings.md` already showed the incumbents are poor value — food stamps beat state pensions
   tenfold on poverty — so there should be a lot to cut without moving the bar.
2. **Lower the taxes.** With spending fixed, find the least taxation that still clears `balance >= 0`,
   two ways: scaling the nine taxes the US actually levies, and spreading the load across all 25.

Usage:
  python scripts/minimum_state.py
  python scripts/minimum_state.py --bar us --step 0.10 --max-cuts 60
"""

from __future__ import annotations

import argparse
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import _cost, _income, evaluate, make_objective
from d3solver.savegame import load_savegame
from d3solver.scenario import anchor_equilibrium, from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")

#: Outcomes to hold, and which direction is "no worse". Kept small and legible on purpose — a bar
#: nobody can read is a bar nobody can argue with.
FLOORS = {
    "Unemployment": "max",   # must not exceed the bar
    "PovertyRate":  "max",
    "CrimeRate":    "max",
    "Health":       "min",   # must not fall below it
    "GDP":          "min",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", type=float, default=0.10, help="how far to cut a policy per move")
    ap.add_argument("--max-cuts", type=int, default=60)
    ap.add_argument("--slack", type=float, default=0.0,
                    help="allow each floor to slip by this much (0 = hold exactly)")
    args = ap.parse_args()

    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    ab = anchored_from_save(save, 1191.0, 1288.0,
                            model=model, anchor_state=anchor_equilibrium(model, scen))
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective({})

    def state_of(settings):
        o, b, eq = evaluate(model, settings, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                            scen.ref_state, scen.ref_active, False)
        inc = sum(_income(n, v, ab, model, eq.values, csv.income_k) for n, v in settings.items())
        cost = sum(_cost(n, v, ab, model, eq.values, csv.cost_k) for n, v in settings.items())
        return eq, inc, cost

    eq0, inc0, cost0 = state_of(scen.policies)
    bar = {k: eq0.values[k] for k in FLOORS}
    print("THE BAR — hold outcomes at the US start:")
    for k, d in FLOORS.items():
        print(f"   {model.sim_values[k].guiname:16s} {bar[k]:.3f}  ({'<=' if d=='max' else '>='})")
    print(f"\nUS start: income ${inc0:.0f}Bn  spending ${cost0:.0f}Bn  balance ${inc0-cost0:+.0f}Bn\n")

    def meets(eq):
        for k, d in FLOORS.items():
            v = eq.values[k]
            if d == "max" and v > bar[k] + args.slack:
                return False
            if d == "min" and v < bar[k] - args.slack:
                return False
        return True

    # ---- stage 1: shrink spending while the bar holds ----------------------------------------
    spenders = [n for n, p in model.policies.items() if p.maxcost > 0]
    cur = dict(scen.policies)
    print("STAGE 1 — cut spending wherever the bar still holds")
    cuts = []
    for _ in range(args.max_cuts):
        _, _, cur_cost = state_of(cur)
        best = None
        for n in spenders:
            v = cur.get(n, 0.0)
            if v <= 1e-9:
                continue
            t = dict(cur); t[n] = max(0.0, v - args.step)
            eq, inc, cost = state_of(t)
            if not meets(eq):
                continue
            saved = cur_cost - cost
            if saved <= 1e-6:
                continue
            if best is None or saved > best[0]:
                best = (saved, n, t[n])
        if best is None:
            break
        saved, n, newv = best
        cur[n] = newv
        cuts.append((model.policies[n].guiname, newv, saved))
    eq1, inc1, cost1 = state_of(cur)
    for g, v, sv in cuts[:18]:
        print(f"   cut {g:26s} -> {v:.2f}   frees ${sv:.0f}Bn")
    if len(cuts) > 18:
        print(f"   ... and {len(cuts)-18} more")
    print(f"\n   spending ${cost0:.0f}Bn -> ${cost1:.0f}Bn   (${cost0-cost1:.0f}Bn cut, "
          f"{100*(cost0-cost1)/cost0:.0f}% of the state)")
    print(f"   bar still met: {meets(eq1)}")
    for k in FLOORS:
        print(f"      {model.sim_values[k].guiname:16s} {bar[k]:.3f} -> {eq1.values[k]:.3f}")

    # ---- stage 2: how little tax funds what is left? ------------------------------------------
    taxes = [n for n, p in model.policies.items() if p.maxincome > 0]
    on = [n for n in taxes if scen.policies.get(n, 0.0) > 1e-9]
    print(f"\nSTAGE 2 — least taxation that still clears balance >= 0 (spending now ${cost1:.0f}Bn)")

    def find(scale_fn, label, lo=0.0, hi=2.0):
        best = None
        for i in range(0, 101):
            k = lo + (hi - lo) * i / 100
            t = dict(cur)
            scale_fn(t, k)
            eq, inc, cost = state_of(t)
            if inc - cost >= 0 and meets(eq):
                best = (k, inc, cost, eq)
                break
        if best is None:
            print(f"   {label}: no level clears the constraint")
            return
        k, inc, cost, eq = best
        print(f"   {label}: {k:.2f}   income ${inc:.0f}Bn  spending ${cost:.0f}Bn  "
              f"balance ${inc-cost:+.0f}Bn  GDP {eq.values['GDP']:.3f}")
        return k

    find(lambda t, k: [t.__setitem__(n, min(1.0, scen.policies[n] * k)) for n in on],
         "scale the 9 existing taxes by      ", 0.0, 2.0)
    find(lambda t, k: [t.__setitem__(n, k) for n in taxes],
         "all 25 taxes at a uniform level of ", 0.0, 1.0)
    find(lambda t, k: [t.__setitem__(n, k) for n in on],
         "the 9 existing at a uniform level  ", 0.0, 1.0)


if __name__ == "__main__":
    main()
