"""Piecewise-linear approximation machinery for the MILP layer.

The effect network is nonlinear only in a small minority of its edges: of the ~1150 incoming edges
built by :func:`d3solver.network.build_full_incoming`, ~89% are **affine** in the source value
(``-0.2+(0.4*x)``) and need no approximation at all. The rest are powers (``x^0.4`` ... ``x^11``) or
products with another node's value. This module supplies exactly what the MILP needs for those:

1. :func:`classify` -- is a formula constant, affine, or genuinely nonlinear over a source's range?
   Affine formulas are lifted to exact ``c0 + c1*x`` coefficients, so they cost the MILP nothing.
2. :func:`build_grid` -- breakpoints for a nonlinear source, chosen by **greedy error-driven
   refinement** rather than a uniform split. This matters: ``x^11`` is flat over most of [0,1] and
   turns almost vertically at the top, so uniform breakpoints waste resolution where the function is
   already a line and lose it exactly where it is not.
3. :class:`Grid` -- the **incremental (delta) formulation** of a piecewise-linear function, which
   needs only ``K-1`` ordinary binaries per grid and no SOS2 support from the solver (CBC via PuLP
   has no dependable SOS2 path).

The decisive structural point is that a grid belongs to a **source node**, not to an edge. Every
formula reading the same source shares one set of ``delta``/``z`` variables, because they are all
functions of the same scalar. That is what keeps the binary count proportional to the ~57 nonlinear
*sources* instead of the ~109 nonlinear *edges*.

Grounding: a formula that cannot be evaluated somewhere in its source's declared range (a fractional
power of a negative base, a division by zero) is **reported**, never silently patched -- the caller
decides, and the exact Layer-1 solver remains the arbiter of what any candidate is really worth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .formula import Formula

# Sampling density for range/curvature analysis. Odd so the midpoint is always sampled.
_SAMPLES = 257
# A formula counts as affine if its deviation from the chord is below this in absolute effect units.
# Effects are small numbers (typically |f| < 1), so this is a tight test, not a permissive one.
_AFFINE_TOL = 1e-9


class RangeError(ValueError):
    """A formula could not be evaluated across the whole of its source node's range."""


@dataclass(frozen=True)
class Affine:
    """An exactly-representable effect: ``c0 + c1 * x``."""

    c0: float
    c1: float

    def at(self, x: float) -> float:
        return self.c0 + self.c1 * x


@dataclass
class Grid:
    """Breakpoints for one source node, plus the incremental-formulation variables built over them.

    The encoding (Markowitz-Manne "delta" form), for breakpoints ``b_0 < b_1 < ... < b_K``::

        x    = b_0 + sum_k (b_k - b_{k-1}) * d_k             d_k in [0, 1]
        f(x) ~ f(b_0) + sum_k (f(b_k) - f(b_{k-1})) * d_k
        d_{k+1} <= z_k <= d_k                                z_k binary

    The ``z`` chain forces the ``d`` to fill left-to-right, so at most one is fractional and the
    interpolation lands on a single segment. ``d`` and ``z`` are shared by every formula reading this
    source; only the ``f(b_k)`` coefficients differ per formula.
    """

    source: str
    lo: float
    hi: float
    breakpoints: list[float]
    deltas: list = field(default_factory=list)   # pulp continuous vars, len K
    zs: list = field(default_factory=list)       # pulp binary vars, len K-1

    @property
    def n_intervals(self) -> int:
        return len(self.breakpoints) - 1

    def x_expr(self):
        """The source value, reconstructed from the deltas (ties the grid to the node variable)."""
        import pulp

        b = self.breakpoints
        return b[0] + pulp.lpSum((b[k + 1] - b[k]) * self.deltas[k] for k in range(self.n_intervals))

    def f_expr(self, values: Sequence[float]):
        """A formula's PWL value, given that formula sampled at each breakpoint."""
        import pulp

        return values[0] + pulp.lpSum(
            (values[k + 1] - values[k]) * self.deltas[k] for k in range(self.n_intervals)
        )


def _safe_eval(f: Formula, x: float, state: Mapping[str, float]) -> float:
    try:
        v = f.evaluate(x, state)
    except Exception as exc:  # noqa: BLE001 - any evaluation failure is a range problem
        raise RangeError(f"{f.source!r} at x={x:.6g}: {exc}") from exc
    if v != v or v in (float("inf"), float("-inf")):  # NaN / inf
        raise RangeError(f"{f.source!r} at x={x:.6g}: non-finite result {v!r}")
    return float(v)


def samples(lo: float, hi: float, n: int = _SAMPLES) -> list[float]:
    if hi <= lo:
        return [lo]
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def evaluate_over(f: Formula, lo: float, hi: float, state: Mapping[str, float],
                  n: int = _SAMPLES) -> list[tuple[float, float]]:
    """Sample ``f`` across [lo, hi]. Raises :class:`RangeError` at the first point it cannot evaluate."""
    return [(x, _safe_eval(f, x, state)) for x in samples(lo, hi, n)]


def classify(f: Formula, lo: float, hi: float, state: Mapping[str, float]) -> Affine | None:
    """Return exact affine coefficients if ``f`` is affine in ``x`` over [lo, hi], else ``None``.

    Uses the chord test at every sample rather than a 3-point check: ``x^2`` is affine at any three
    symmetric points about the midpoint of a symmetric interval, so a sparse test would misclassify it.
    """
    pts = evaluate_over(f, lo, hi, state)
    if len(pts) == 1:
        return Affine(pts[0][1], 0.0)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    slope = (y1 - y0) / (x1 - x0) if x1 != x0 else 0.0
    for x, y in pts:
        if abs(y - (y0 + slope * (x - x0))) > _AFFINE_TOL:
            return None
    return Affine(c0=y0 - slope * x0, c1=slope)


def value_range(f: Formula, lo: float, hi: float, state: Mapping[str, float]) -> tuple[float, float]:
    """Min/max of ``f`` over the source's range -- used for tight big-M and for clamp elision."""
    ys = [y for _, y in evaluate_over(f, lo, hi, state)]
    return min(ys), max(ys)


def _interp(curve: Sequence[tuple[float, float]], x: float) -> float:
    """Linear interpolation of a sampled curve at ``x`` (curve is sorted by x)."""
    if x <= curve[0][0]:
        return curve[0][1]
    if x >= curve[-1][0]:
        return curve[-1][1]
    lo_i, hi_i = 0, len(curve) - 1
    while hi_i - lo_i > 1:
        mid = (lo_i + hi_i) // 2
        if curve[mid][0] <= x:
            lo_i = mid
        else:
            hi_i = mid
    (x0, y0), (x1, y1) = curve[lo_i], curve[hi_i]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def build_grid(source: str, lo: float, hi: float, formulas: Sequence[Formula],
               state: Mapping[str, float], intervals: int = 8) -> Grid:
    """Choose breakpoints for ``source`` by greedy error-driven refinement.

    Start with the single interval [lo, hi]; repeatedly split whichever interval carries the largest
    piecewise-linear error, at the point where that error peaks. Error is the **worst absolute
    deviation across all formulas reading this source**, which is the right metric because effects are
    summed additively into a node -- an absolute error of 0.01 is worth the same wherever it comes from.
    """
    if hi <= lo:
        return Grid(source=source, lo=lo, hi=hi, breakpoints=[lo, lo + 1e-9])

    curves = [evaluate_over(f, lo, hi, state) for f in formulas]
    bps = [lo, hi]
    for _ in range(max(0, intervals - 1)):
        worst_err, worst_at, worst_iv = -1.0, None, None
        for i in range(len(bps) - 1):
            a, b = bps[i], bps[i + 1]
            for curve in curves:
                ya, yb = _interp(curve, a), _interp(curve, b)
                for x, y in curve:
                    if x <= a or x >= b:
                        continue
                    t = (x - a) / (b - a)
                    err = abs(y - (ya + t * (yb - ya)))
                    if err > worst_err:
                        worst_err, worst_at, worst_iv = err, x, i
        if worst_at is None or worst_err <= _AFFINE_TOL:
            break  # already exact -- more breakpoints would only cost binaries
        bps.insert(worst_iv + 1, worst_at)
        bps.sort()
    return Grid(source=source, lo=lo, hi=hi, breakpoints=bps)


def grid_error(grid: Grid, f: Formula, state: Mapping[str, float]) -> float:
    """Worst absolute PWL error of ``f`` on ``grid`` -- the honest accuracy number to report."""
    curve = evaluate_over(f, grid.lo, grid.hi, state)
    node_vals = [_interp(curve, b) for b in grid.breakpoints]
    worst = 0.0
    for x, y in curve:
        for k in range(grid.n_intervals):
            a, b = grid.breakpoints[k], grid.breakpoints[k + 1]
            if a <= x <= b:
                t = 0.0 if b == a else (x - a) / (b - a)
                worst = max(worst, abs(y - (node_vals[k] + t * (node_vals[k + 1] - node_vals[k]))))
                break
    return worst


def sample_at(f: Formula, xs: Sequence[float], state: Mapping[str, float]) -> list[float]:
    """Evaluate ``f`` at the given breakpoints (the PWL coefficients for one formula on a grid)."""
    return [_safe_eval(f, x, state) for x in xs]


__all__ = ["Affine", "Grid", "RangeError", "build_grid", "classify", "evaluate_over",
           "grid_error", "sample_at", "samples", "value_range"]
