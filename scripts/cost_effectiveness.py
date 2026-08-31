"""What does each policy deliver per $Bn, for a target you name?

`notes/findings.md` established that military spending buys jobs and state pensions buy poverty
reduction. That is not the interesting question. The interesting question is **whether they are good
value**, because everything in this model buys something and the budget is finite: paying people to
march around is *a* way to reduce unemployment, and compelling saving is *a* way to reduce poverty,
but the money could be spent on the same outcomes somewhere else.

So this ranks every policy by outcome-per-dollar against a target, and puts the incumbent programmes
on the same scale as their alternatives.

Two measures, because they answer different questions:

* **Average value** - remove the policy entirely and compare. This is the "should this programme
  exist at all?" number, and it is the right one for judging a $248Bn line item.
* **Marginal value** - nudge it from where it currently sits. This is the shadow-price number
  `notes/scope.md` describes, and the right one for "where should the next dollar go?". They differ
  whenever a policy has diminishing returns, which most of them do.

Sign convention: *improvement* means the weighted target went up, so pass negative weights for things
you want less of (`Unemployment: -1`). *Spend* is the fall in budget balance, so a policy that
improves the target **and** the balance is a free win and is reported separately rather than being
given a meaningless per-dollar ratio.

Usage:
  python scripts/cost_effectiveness.py --target jobs
  python scripts/cost_effectiveness.py --target poverty --top 20
  python scripts/cost_effectiveness.py --target jobs --replace MilitarySpending
"""

from __future__ import annotations

import argparse
from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import evaluate, make_objective
from d3solver.savegame import load_savegame
from d3solver.scenario import from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")

TARGETS = {
    "jobs":     ({"Unemployment": -1.0}, "less unemployment"),
    "poverty":  ({"PovertyRate": -1.0}, "less poverty"),
    "both":     ({"Unemployment": -1.0, "PovertyRate": -1.0}, "less unemployment and poverty"),
    "crime":    ({"CrimeRate": -1.0}, "less crime"),
    "health":   ({"Health": 1.0}, "better health"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=sorted(TARGETS), default="jobs")
    ap.add_argument("--step", type=float, default=0.15, help="marginal perturbation size")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--replace", default=None,
                    help="a policy to zero out, then buy its target effect back with the best value")
    ap.add_argument("--max-moves", type=int, default=60)
    args = ap.parse_args()

    weights, label = TARGETS[args.target]
    model = load_model(sim_dir())
    save = load_savegame(SAVE)
    scen = from_savegame(save)
    ab = anchored_from_save(save, 1191.0, 1288.0)
    csv = calibrate(model, scen.policies, dict(save.sim_values), 1191.0, 1288.0)
    obj = make_objective(weights)

    def ev(settings):
        return evaluate(model, settings, scen.exogenous, obj, ab, csv.cost_k, csv.income_k,
                        scen.ref_state, scen.ref_active, False)

    base_obj, base_bal, base_eq = ev(scen.policies)
    print(f"TARGET: {label}   (weights {weights})")
    print(f"US start: target score {base_obj:+.4f}, balance ${base_bal:+.0f}Bn\n")

    # ---- average value: what is each enacted policy's whole programme worth per $? -------------
    print(f"AVERAGE VALUE of the programmes that are actually running")
    print("  (remove it entirely; how much target did the whole budget line buy?)\n")
    print(f"  {'policy':26s} {'level':>6s} {'frees $':>9s} {'target lost':>12s} {'per $100Bn':>11s}")
    print("  " + "-" * 68)
    rows = []
    for n, v in scen.policies.items():
        if v <= 1e-9:
            continue
        st = dict(scen.policies); st[n] = 0.0
        o, b, _ = ev(st)
        freed = b - base_bal                      # >0 means removing it frees money
        lost = base_obj - o                       # >0 means the programme was doing good
        if freed <= 1e-6:
            continue                              # not a spending programme at this level
        rows.append((lost / freed * 100.0, n, v, freed, lost))
    rows.sort(reverse=True)
    for eff, n, v, freed, lost in rows[:args.top]:
        print(f"  {model.policies[n].guiname[:26]:26s} {v:6.2f} {freed:+8.0f}B {lost:+12.4f} {eff:11.4f}")
    print("\n  ^ higher = better value for money. A negative 'target lost' means removing it")
    print("    would IMPROVE the target as well as free the money.\n")

    # ---- marginal value: where should the next dollar go? --------------------------------------
    print(f"MARGINAL VALUE at the current operating point (+{args.step:.2f} on each policy)\n")
    buys, frees = [], []
    for n in model.policies:
        s = scen.policies.get(n, 0.0)
        new = min(1.0, s + args.step)
        if abs(new - s) < 1e-9:
            continue
        st = dict(scen.policies); st[n] = new
        o, b, _ = ev(st)
        d_obj, d_bal = o - base_obj, b - base_bal
        if d_obj <= 1e-6:
            continue                              # does not help the target
        if d_bal >= -1e-6:
            frees.append((d_obj, n, d_bal))       # helps the target AND pays for itself
        else:
            buys.append((d_obj / (-d_bal) * 100.0, n, d_obj, -d_bal))

    frees.sort(reverse=True)
    print(f"  FREE WINS - improve {label} and do not cost money ({len(frees)} of them)")
    if frees:
        print(f"  {'policy':26s} {'target gain':>12s} {'balance':>10s}")
        for d_obj, n, d_bal in frees[:args.top]:
            print(f"  {model.policies[n].guiname[:26]:26s} {d_obj:+12.4f} {d_bal:+9.0f}B")
    else:
        print("  (none)")

    buys.sort(reverse=True)
    print(f"\n  BEST BUYS - improve {label} for money ({len(buys)} of them)")
    print(f"  {'policy':26s} {'target gain':>12s} {'costs':>9s} {'per $100Bn':>11s}")
    for eff, n, d_obj, spend in buys[:args.top]:
        print(f"  {model.policies[n].guiname[:26]:26s} {d_obj:+12.4f} {spend:8.0f}B {eff:11.4f}")

    # ---- replacement: cut a programme, buy the same effect back the cheapest way ---------------
    if args.replace:
        rep = args.replace
        if rep not in model.policies:
            print(f"\nunknown policy {rep!r}")
            return
        print(f"\n\nREPLACEMENT TEST - cut {model.policies[rep].guiname}, then buy the lost "
              f"{label} back\n")
        st = dict(scen.policies); st[rep] = 0.0
        o0, b0, _ = ev(st)
        print(f"  after the cut: target {o0:+.4f} (was {base_obj:+.4f}), "
              f"balance ${b0:+.0f}Bn (was ${base_bal:+.0f}Bn)")
        print(f"  need to recover {base_obj - o0:+.4f} of target; have ${b0 - base_bal:+.0f}Bn to spend\n")

        cand = [n for n in model.policies if n != rep]
        moves = []
        for _ in range(args.max_moves):
            cur_o, cur_b, _ = ev(st)
            if cur_o >= base_obj:
                break
            best = None
            for n in cand:
                s = st.get(n, 0.0)
                new = min(1.0, s + args.step)
                if abs(new - s) < 1e-9:
                    continue
                t = dict(st); t[n] = new
                o, b, _ = ev(t)
                d_obj, d_bal = o - cur_o, b - cur_b
                if d_obj <= 1e-4:
                    continue          # a move worth +0.0000 is not worth a slot
                # Free moves outrank paid ones, but among free moves prefer the BIGGEST gain, not an
                # arbitrary one -- they all divide by zero cost, so the ratio cannot order them.
                score = (1, d_obj) if d_bal >= 0 else (0, d_obj / max(1e-6, -d_bal))
                if best is None or score > best[0]:
                    best = (score, n, new, d_obj, d_bal)
            if best is None:
                print("  no further improving move available")
                break
            _, n, new, d_obj, d_bal = best
            st[n] = new
            moves.append((n, new, d_obj, d_bal))

        fo, fb, feq = ev(st)
        print(f"  {'move':28s} {'to':>5s} {'target':>10s} {'balance':>10s}")
        for n, new, d_obj, d_bal in moves:
            print(f"  {model.policies[n].guiname[:28]:28s} {new:5.2f} {d_obj:+10.4f} {d_bal:+9.0f}B")
        print(f"\n  RESULT: target {base_obj:+.4f} -> {fo:+.4f}   "
              f"balance ${base_bal:+.0f}Bn -> ${fb:+.0f}Bn")
        recovered = (fo - o0) / max(1e-9, base_obj - o0) * 100.0
        print(f"  recovered {recovered:.0f}% of what the cut lost, and the budget is "
              f"${fb - base_bal:+.0f}Bn better than where it started.")
        if fo >= base_obj and fb > base_bal:
            print(f"\n  VERDICT: {model.policies[rep].guiname} is NOT the efficient way to buy "
                  f"{label} -\n  the same outcome is available for ${fb - base_bal:.0f}Bn less.")
        elif fo < base_obj:
            print(f"\n  VERDICT: could not fully replace it within {args.max_moves} moves - "
                  f"{model.policies[rep].guiname}\n  is doing something the alternatives do not reach.")


if __name__ == "__main__":
    main()
