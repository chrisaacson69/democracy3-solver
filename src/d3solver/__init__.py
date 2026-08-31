"""d3solver — game-data + optimization approach to "solving" Democracy 3.

Layer 1 (this package, in progress): faithfully parse the game's own CSVs and simulate the
equilibrium state + vote share for any policy vector. This is the grounded oracle.
Layer 2 (later): an optimizer (linearized LP for marginals; MILP / piecewise for a global solve)
that proposes policy vectors, each scored by Layer 1.
"""

from __future__ import annotations

from .formula import Formula, FormulaError, parse_formula
from .loader import load_model
from .model import Effect, GameModel, Policy, SimValue, VoterType

__all__ = [
    "Formula", "FormulaError", "parse_formula",
    "load_model",
    "Effect", "GameModel", "Policy", "SimValue", "VoterType",
]
