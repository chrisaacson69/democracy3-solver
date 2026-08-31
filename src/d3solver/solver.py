"""Iterative equilibrium solver — the counterfactual fixed point of the effect network.

Given a policy vector and exogenous parameters (the world-economy position, political globals), iterate

    node_value ← clamp( default + Σ influenceᵢ ,  min, max )

over all endogenous nodes (simulation values, voter groups, situation values) until it settles. This
is a *counterfactual* steady state — where the model would rest if policies were fully implemented and
the economy sat at the given (default: average) position. The live game never sits here; that's fine,
we optimize the stable core and let savings buffer the economic cycle (see notes/scope.md).

Inertia is ignored: at a fixed point the moving average equals the current value.
Situations are solved self-consistently via hysteresis (active above start_trigger, off below
stop_trigger); an inactive situation's *output* effects don't apply.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import GameModel
from .network import build_full_incoming

_CONST = "_default_"  # constant-base token in situation inputs (its formula ignores x)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class Equilibrium:
    values: dict[str, float]                       # node name -> settled value
    active: dict[str, bool]                         # situation name -> active
    iterations: int
    max_delta: float
    converged: bool
    unresolved: set[str] = field(default_factory=set)  # sources defaulted to 0 (reported, not hidden)


def solve_equilibrium(
    model: GameModel,
    policies: dict[str, float],
    exogenous: dict[str, float],
    *,
    max_iter: int = 2000,
    eps: float = 1e-6,
    damping: float = 0.5,
    init_values: dict[str, float] | None = None,
    init_active: dict[str, bool] | None = None,
    freeze_active: bool = False,
) -> Equilibrium:
    incoming = build_full_incoming(model)

    # Fixed inputs the solve reads but never updates.
    fixed: dict[str, float] = dict(exogenous)
    fixed.update(policies)
    fixed[_CONST] = 0.0  # placeholder; _default_ input formulas are constants that ignore x

    # Endogenous nodes: (default, min, max).
    meta: dict[str, tuple[float, float, float]] = {}
    for n, sv in model.sim_values.items():
        meta[n] = (sv.default, sv.min, sv.max)
    for n, vt in model.voter_types.items():
        meta[n] = (vt.default, -1.0, 1.0)          # group clamp assumption (see scope open items)
    for n in model.situations:
        meta[n] = (0.0, 0.0, 1.0)                   # situation base is 0; its _default_ input adds the base

    state: dict[str, float] = dict(fixed)
    for n, (d, lo, hi) in meta.items():
        start = init_values[n] if (init_values and n in init_values) else d
        state[n] = _clamp(start, lo, hi)
    active: dict[str, bool] = {n: bool(init_active.get(n, False)) if init_active else False
                              for n in model.situations}
    unresolved: set[str] = set()

    def value_of(src: str) -> float:
        if src in state:
            return state[src]
        unresolved.add(src)
        return 0.0

    it = 0
    max_delta = 0.0
    for it in range(1, max_iter + 1):
        # hysteresis: update situation activation from current values (unless frozen)
        if not freeze_active:
            for n in model.situations:
                sit = model.situations[n]
                if not active[n] and state[n] >= sit.start_trigger:
                    active[n] = True
                elif active[n] and state[n] < sit.stop_trigger:
                    active[n] = False

        new: dict[str, float] = {}
        for n, (d, lo, hi) in meta.items():
            total = d
            for e in incoming.get(n, []):
                if e.source in active and not active[e.source]:
                    continue  # inactive situation exerts nothing
                total += e.formula.evaluate(value_of(e.source), state)
            new[n] = _clamp(total, lo, hi)

        max_delta = 0.0
        for n in meta:
            updated = state[n] + damping * (new[n] - state[n])
            max_delta = max(max_delta, abs(updated - state[n]))
            state[n] = updated

        if max_delta < eps:
            break

    return Equilibrium(
        values={n: state[n] for n in meta},
        active=active,
        iterations=it,
        max_delta=max_delta,
        converged=max_delta < eps,
        unresolved=unresolved,
    )


__all__ = ["Equilibrium", "solve_equilibrium"]
