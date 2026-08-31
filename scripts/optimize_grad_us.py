"""Gradient optimizer on the US save, from two starting points, to test speed/convergence and whether
distinct starts find the same optimum or alternate policy paths.
"""

from __future__ import annotations

from pathlib import Path

from d3solver import load_model
from d3solver.budget import anchored_from_save, calibrate
from d3solver.config import sim_dir
from d3solver.optimize import make_objective, gradient_optimize
from d3solver.savegame import load_savegame
from d3solver.scenario import from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")
WEIGHTS = {"Equality": 1.0, "Health": 1.0, "PovertyRate": -1.0, "Unemployment": -1.0, "CrimeRate": -1.0}


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

    starts = {
        "from status-quo": dict(cur),
        "from minimal-gov": {n: (0.1 if v > 0 else 0.0) for n, v in cur.items()},  # shrink everything
    }
    results = {}
    for label, p0 in starts.items():
        res = gradient_optimize(model, p0, exo, obj, ab, csv.cost_k, csv.income_k,
                                init_values=seed_state, init_active=seed_active, freeze_active=True)
        results[label] = res
        t = res["trace"]
        print(f"[{label}] steps={len(t)} X={res['obj']:.3f} balance=${res['balance']:.0f}Bn "
              f"final_gnorm={t[-1]['gnorm']:.4f}")

    print()
    for label, res in results.items():
        print(f"--- {label}: top policy settings (>0.5 or changed a lot) ---")
        p = res["settings"]
        rows = sorted(p.items(), key=lambda kv: kv[1], reverse=True)
        print("  high: " + ", ".join(f"{n}={v:.2f}" for n, v in rows[:12] if v > 0.5))


if __name__ == "__main__":
    main()
