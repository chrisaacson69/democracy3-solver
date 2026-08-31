"""Run the equilibrium solver on the US policy set and compare to the save.

The save is turn-1 (mid-transient); our solver computes the counterfactual fixed point for the same
policies + economy. Differences are the transient the game hasn't settled yet — largest for
high-inertia / still-ramping nodes.

Usage: PYTHONPATH=src python scripts/solve_us.py [save.xml]
"""

from __future__ import annotations

import sys
from pathlib import Path

from d3solver import load_model
from d3solver.config import sim_dir
from d3solver.savegame import load_savegame
from d3solver.solver import solve_equilibrium

DEFAULT_SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")


def main() -> None:
    positional = [a for a in sys.argv[1:] if not a.startswith("--")]
    save_path = Path(positional[0]) if positional else DEFAULT_SAVE
    model = load_model(sim_dir())
    save = load_savegame(save_path)

    policies = {n: d["val"] for n, d in save.policies.items()}
    exo = {
        "_global_socialism": save.globals.get("socialism", 0.5),
        "_global_liberalism": save.globals.get("liberalism", 0.5),
        "_globaleconomy_": save.globals.get("globaleconomy_pos", 0.5),
        "_year": save.globals.get("globaleconomy_years", 0.0),
    }

    warm = "--warm" in sys.argv
    init_values = None
    init_active = None
    if warm:
        init_values = dict(save.sim_values)
        init_values.update({n: d["val"] for n, d in save.situations.items()})  # seed situation values too
        init_active = {n: bool(d["active"]) for n, d in save.situations.items()}
    print(f"[{'WARM-START from save' if warm else 'COLD-START from defaults'}]")

    eq = solve_equilibrium(model, policies, exo, init_values=init_values, init_active=init_active)
    print(f"converged={eq.converged}  iterations={eq.iterations}  max_delta={eq.max_delta:.2e}")
    print(f"active situations solved: {sorted(n for n, a in eq.active.items() if a)}")
    if eq.unresolved:
        print(f"unresolved sources (treated as 0): {sorted(eq.unresolved)}")

    # Compare solved sim values to the (transient) save.
    rows = []
    for n in model.sim_values:
        solved = eq.values[n]
        actual = save.sim_values.get(n)
        if actual is not None:
            rows.append((n, actual, solved, abs(actual - solved)))
    rows.sort(key=lambda r: r[3], reverse=True)

    print(f"\n{'node':22s} {'save(turn1)':>11s} {'solved(eq)':>11s} {'diff':>7s}")
    print("-" * 56)
    for n, a, s, d in rows:
        print(f"{n:22s} {a:11.4f} {s:11.4f} {d:7.4f}")
    print("-" * 56)
    print(f"mean |diff| vs transient save: {sum(r[3] for r in rows)/len(rows):.4f}")


if __name__ == "__main__":
    main()
