"""Typed representation of the Democracy 3 simulation model.

These dataclasses mirror the CSV grammar documented in ``notes/grammar.md``. They are the parsed,
in-memory form of the game's own data files — the single source of truth the simulator and optimizer
both read from.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .formula import Formula


@dataclass(frozen=True)
class Effect:
    """A directed effect: source node exerts ``formula(x)`` on ``target``, lagged by ``inertia``."""

    target: str
    formula: Formula
    inertia: int = 0  # turns to ramp to full strength; 0 = instant

    @property
    def source_text(self) -> str:
        return self.formula.source


@dataclass
class SimValue:
    """A derived simulation value (GDP, CrimeRate, ...)."""

    name: str
    guiname: str
    description: str
    zone: str
    default: float
    min: float
    max: float
    emotion: str  # HIGHGOOD | HIGHBAD | UNKNOWN | HIDDEN
    inputs: list[Effect] = field(default_factory=list)   # effects into this node
    outputs: list[Effect] = field(default_factory=list)  # effects this node exerts


@dataclass
class Policy:
    """A player-controlled policy (the decision variables)."""

    name: str
    guiname: str
    slider: str
    description: str
    flags: list[str]
    department: str
    mincost: float
    maxcost: float
    cost_multiplier: str  # raw multiplier expression list; parsed lazily in the budget layer
    implementation: int
    minincome: float
    maxincome: float
    income_multiplier: str
    effects: list[Effect] = field(default_factory=list)

    @property
    def is_tax(self) -> bool:
        return self.maxincome > 0 or self.slider == "tax"


@dataclass
class VoterType:
    """A voter group — the objective is built from these."""

    name: str
    guiname: str
    plural: str
    default: float       # baseline happiness bias
    percentage: float    # population share (membership weight)
    description: str
    influences: dict[str, float] = field(default_factory=dict)  # cross-membership weights


@dataclass
class Situation:
    """A threshold-triggered emergent state (recession, crime wave, ...).

    Its value is driven by ``inputs`` like any node; it switches on above ``start_trigger`` and off
    below ``stop_trigger`` (hysteresis). While active it exerts ``outputs`` on other nodes.
    """

    name: str
    guiname: str
    start_trigger: float
    stop_trigger: float
    positive: bool
    inputs: list[Effect] = field(default_factory=list)   # token names the SOURCE driving this
    outputs: list[Effect] = field(default_factory=list)  # effects exerted while active


@dataclass
class GameModel:
    """The whole parsed model plus any non-fatal parse problems encountered."""

    sim_values: dict[str, SimValue] = field(default_factory=dict)
    policies: dict[str, Policy] = field(default_factory=dict)
    voter_types: dict[str, VoterType] = field(default_factory=dict)
    situations: dict[str, Situation] = field(default_factory=dict)
    # (name, field, raw, reason) for every row/effect we could not parse — surfaced, never hidden.
    problems: list[tuple[str, str, str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{len(self.sim_values)} sim values, {len(self.policies)} policies, "
            f"{len(self.voter_types)} voter types, {len(self.situations)} situations, "
            f"{len(self.problems)} parse problems"
        )


__all__ = ["Effect", "SimValue", "Policy", "VoterType", "Situation", "GameModel"]
