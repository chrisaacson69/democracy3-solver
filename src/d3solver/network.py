"""Build the effect network's incoming-edge index from the parsed model.

Effects are declared scattered across the CSVs and in both directions, so we normalize them into a
single map ``target -> [(source, formula, inertia), ...]``. Direction rules (see notes/grammar.md):

- simulation.csv, node N:
    * an **output** token ``(T, f)``  → edge  N → T   (source = N)
    * an **input**  token ``(S, f)``  → edge  S → N   (source = S; the token names the SOURCE)
- policies.csv, policy P: each effect ``(T, f)`` → edge  P → T   (source = P)

This is the reverse adjacency the equilibrium solve needs: a node's value is a function of the values
of everything with an edge into it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .formula import Formula
from .model import GameModel


@dataclass(frozen=True)
class IncomingEdge:
    source: str
    formula: Formula
    inertia: int = 0


def build_incoming(
    model: GameModel,
    active_situations: dict[str, float] | None = None,
) -> dict[str, list[IncomingEdge]]:
    """Reverse adjacency: target -> incoming edges.

    ``active_situations`` (name -> current value) adds each active situation's *output* effects as
    edges. Inactive situations contribute nothing (their effects only apply while triggered).
    """
    incoming: dict[str, list[IncomingEdge]] = {}

    def add(source: str, target: str, formula: Formula, inertia: int) -> None:
        incoming.setdefault(target, []).append(IncomingEdge(source, formula, inertia))

    for name, sv in model.sim_values.items():
        for e in sv.outputs:            # N -> e.target
            add(name, e.target, e.formula, e.inertia)
        for e in sv.inputs:             # token names the source; target is this node
            add(e.target, name, e.formula, e.inertia)

    for name, p in model.policies.items():
        for e in p.effects:             # P -> e.target
            add(name, e.target, e.formula, e.inertia)

    if active_situations:
        for sname in active_situations:
            sit = model.situations.get(sname)
            if sit is None:
                continue
            for e in sit.outputs:       # active situation -> e.target
                add(sname, e.target, e.formula, e.inertia)

    return incoming


def build_full_incoming(model: GameModel) -> dict[str, list[IncomingEdge]]:
    """Complete reverse adjacency for the solver: sim in/out, policy effects, and situation
    **inputs** (drive the situation's value) **and outputs** (its effects; the solver gates these by
    the situation's active flag at runtime). Unlike :func:`build_incoming`, all situations are included
    unconditionally — activation is decided during the solve.
    """
    incoming: dict[str, list[IncomingEdge]] = {}

    def add(source: str, target: str, formula, inertia: int) -> None:
        incoming.setdefault(target, []).append(IncomingEdge(source, formula, inertia))

    for name, sv in model.sim_values.items():
        for e in sv.outputs:
            add(name, e.target, e.formula, e.inertia)
        for e in sv.inputs:
            add(e.target, name, e.formula, e.inertia)
    for name, p in model.policies.items():
        for e in p.effects:
            add(name, e.target, e.formula, e.inertia)
    for name, s in model.situations.items():
        for e in s.inputs:                       # source token -> situation value
            add(e.target, name, e.formula, e.inertia)
        for e in s.outputs:                      # situation -> target (gate by active at runtime)
            add(name, e.target, e.formula, e.inertia)
    return incoming


__all__ = ["IncomingEdge", "build_incoming", "build_full_incoming"]
