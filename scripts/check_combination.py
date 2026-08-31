"""Empirically resolve the combination rule against the savegame oracle.

The save is the game's fixed point. For each simulation value we compute what the additive model
predicts from the *saved* source values, and compare to the saved value itself. Two hypotheses:

    H1 (default + sum): value = clamp(default + sum influence_i)
    H2 (sum only):      value = clamp(sum influence_i)

Nodes whose direct sources aren't all available in the save (voter groups, unknown globals) are
SKIPPED and listed — never faked.

Usage:  PYTHONPATH=src python scripts/check_combination.py [path-to-autosave.xml]
"""

from __future__ import annotations

import sys
from pathlib import Path

from d3solver import load_model
from d3solver.config import sim_dir
from d3solver.network import build_incoming
from d3solver.savegame import load_savegame

DEFAULT_SAVE = Path.home() / "OneDrive/Documents/My Games/democracy3/savegames/autosave.xml"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def main() -> None:
    save_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAVE
    model = load_model(sim_dir())
    save = load_savegame(save_path)

    active_sits = save.active_situations()
    incoming = build_incoming(model, active_situations=active_sits)

    # State = every value the save gives us that a formula might read as a source.
    state: dict[str, float] = {}
    state.update(save.sim_values)                                   # 40 sim values
    state.update({k: v["val"] for k, v in save.policies.items()})   # 123 policy settings
    # all situations as possible sources: active use their value, inactive contribute 0
    state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})
    if "socialism" in save.globals:
        state["_global_socialism"] = save.globals["socialism"]
    if "liberalism" in save.globals:
        state["_global_liberalism"] = save.globals["liberalism"]
    if "globaleconomy_pos" in save.globals:
        state["_globaleconomy_"] = save.globals["globaleconomy_pos"]
    if "globaleconomy_years" in save.globals:
        state["_year"] = save.globals["globaleconomy_years"]

    def missing_source(edges):
        for e in edges:
            if e.source not in state:
                return e.source
            for ref in e.formula.refs:
                if ref not in state:
                    return ref
        return None

    rows, skipped = [], []
    for name, sv in model.sim_values.items():
        edges = incoming.get(name, [])
        miss = missing_source(edges)
        if miss is not None:
            skipped.append((name, miss, len(edges)))
            continue
        total = 0.0
        for e in edges:
            total += e.formula.evaluate(state[e.source], state)
        h1 = clamp(sv.default + total, sv.min, sv.max)
        h2 = clamp(total, sv.min, sv.max)
        actual = save.sim_values[name]
        rows.append((name, actual, h1, h2, len(edges)))

    print(f"Resolvable nodes: {len(rows)} | skipped (missing source): {len(skipped)}\n")
    print(f"{'node':22s} {'actual':>8s} {'H1:def+sum':>9s} {'err1':>7s} {'H2:sum':>8s} {'err2':>7s} {'#in':>4s}")
    print("-" * 70)
    e1sum = e2sum = 0.0
    for name, actual, h1, h2, n in sorted(rows, key=lambda r: abs(r[1] - r[2]), reverse=True):
        err1, err2 = abs(actual - h1), abs(actual - h2)
        e1sum += err1; e2sum += err2
        print(f"{name:22s} {actual:8.4f} {h1:9.4f} {err1:7.4f} {h2:8.4f} {err2:7.4f} {n:4d}")
    if rows:
        print("-" * 70)
        print(f"mean abs err — H1 (default+sum): {e1sum/len(rows):.4f}   H2 (sum only): {e2sum/len(rows):.4f}")

    print("\nSkipped (node, first missing source, #edges):")
    for name, miss, n in skipped:
        print(f"   {name:22s} missing={miss:20s} ({n} edges)")


if __name__ == "__main__":
    main()
