"""Effect-formula parser and evaluator for Democracy 3 simulation data.

A formula is an arithmetic expression in the source node's normalized value ``x``, e.g.
``-0.2+(0.4*x)``, ``0.98*(x^4)``, ``0.25*(x^5)*Narcotics``. Bare identifiers other than ``x`` are
references to other nodes' current values (used as multipliers). ``^`` means exponentiation.

We compile each formula to a Python AST once (via a whitelisted subset), then evaluate it against a
state mapping. This is a *conversion* of the grounded CSV grammar, not a rebuild — the CSVs remain
the source of truth, and every formula round-trips through here so bad ones surface instead of being
silently guessed at.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Mapping

# AST node types we permit. Anything else in a formula is a hard error (surface it, don't guess).
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Name,
    ast.Load,
)


class FormulaError(ValueError):
    """Raised when a formula string cannot be parsed as a valid effect expression."""


@dataclass(frozen=True)
class Formula:
    """A parsed, reusable effect formula.

    ``source`` is the original string (kept for provenance/debugging). ``refs`` is the set of node
    names the formula reads besides ``x`` (empty for the common per-node polynomial case).
    """

    source: str
    _code: object  # compiled code object
    refs: frozenset[str]

    def evaluate(self, x: float, state: Mapping[str, float] | None = None) -> float:
        """Evaluate the formula. ``x`` is the source node's value; ``state`` resolves any refs."""
        env = {"x": float(x)}
        if self.refs:
            if state is None:
                raise FormulaError(
                    f"formula {self.source!r} references {sorted(self.refs)} but no state was given"
                )
            for name in self.refs:
                if name not in state:
                    raise FormulaError(
                        f"formula {self.source!r} references unknown node {name!r}"
                    )
                env[name] = float(state[name])
        # eval of a pre-vetted code object over a fixed env; no builtins exposed.
        return float(eval(self._code, {"__builtins__": {}}, env))  # noqa: S307 - vetted AST


def _collect_refs(tree: ast.AST) -> frozenset[str]:
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names.discard("x")
    return frozenset(names)


def parse_formula(source: str) -> Formula:
    """Parse a Democracy 3 effect formula string into a reusable :class:`Formula`.

    Raises :class:`FormulaError` on anything malformed (e.g. the shipped ``0.0.5`` typo), so callers
    can record and skip the bad row rather than fabricate a value.
    """
    raw = (source or "").strip()
    if not raw:
        raise FormulaError("empty formula")
    # Democracy 3 uses '^' for exponentiation; Python uses '**'.
    py = raw.replace("^", "**")
    try:
        tree = ast.parse(py, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"cannot parse formula {source!r}: {exc.msg}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise FormulaError(
                f"formula {source!r} uses disallowed construct {type(node).__name__}"
            )
        # Reject non-numeric constants (strings etc.).
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise FormulaError(f"formula {source!r} has non-numeric constant {node.value!r}")
    refs = _collect_refs(tree)
    code = compile(tree, filename="<formula>", mode="eval")
    return Formula(source=raw, _code=code, refs=refs)


__all__ = ["Formula", "FormulaError", "parse_formula", "math"]
