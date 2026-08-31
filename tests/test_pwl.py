"""Tests for the piecewise-linear layer.

The point of these is that the MILP's fidelity rests entirely on two claims: that affine formulas are
recognised exactly (so ~89% of the network costs no binaries and carries no error), and that the
breakpoint refinement actually drives the error down on the ones that are not.
"""

from __future__ import annotations

import math

import pytest

from d3solver.formula import parse_formula
from d3solver.pwl import (Affine, RangeError, build_grid, classify, grid_error, sample_at,
                          value_range)


def test_affine_is_recognised_exactly():
    f = parse_formula("-0.2+(0.4*x)")
    aff = classify(f, 0.0, 1.0, {})
    assert isinstance(aff, Affine)
    assert aff.c0 == pytest.approx(-0.2)
    assert aff.c1 == pytest.approx(0.4)


def test_constant_is_affine_with_zero_slope():
    aff = classify(parse_formula("0.35"), 0.0, 1.0, {})
    assert aff is not None and aff.c1 == pytest.approx(0.0) and aff.c0 == pytest.approx(0.35)


@pytest.mark.parametrize("src", ["0.98*(x^4)", "0.30*(x^0.6)+0.07", "0-(x^11)", "-0.2*(x^2)+0.05"])
def test_powers_are_not_mistaken_for_affine(src):
    """A 3-point chord test would call x^2 affine on a symmetric interval; the dense test must not."""
    assert classify(parse_formula(src), 0.0, 1.0, {}) is None


def test_refinement_reduces_error_monotonically():
    f = parse_formula("0.98*(x^4)")
    errs = [grid_error(build_grid("S", 0.0, 1.0, [f], {}, intervals=k), f, {})
            for k in (1, 2, 4, 8, 16)]
    assert errs == sorted(errs, reverse=True), errs
    assert errs[-1] < errs[0] / 20


def test_refinement_beats_uniform_on_a_sharp_curve():
    """x^11 is the case error-driven placement exists for: flat, then near-vertical at the top."""
    f = parse_formula("0-(x^11)")
    adaptive = build_grid("S", 0.0, 1.0, [f], {}, intervals=8)
    uniform = build_grid("S", 0.0, 1.0, [f], {}, intervals=8)
    uniform.breakpoints = [i / 8 for i in range(9)]
    assert grid_error(adaptive, f, {}) < grid_error(uniform, f, {})


def test_breakpoints_are_sorted_and_span_the_range():
    g = build_grid("S", -1.0, 1.0, [parse_formula("0.5*(x^2)")], {}, intervals=6)
    assert g.breakpoints == sorted(g.breakpoints)
    assert g.breakpoints[0] == pytest.approx(-1.0)
    assert g.breakpoints[-1] == pytest.approx(1.0)
    assert g.n_intervals == 6


def test_grid_is_shared_across_formulas_of_one_source():
    """One grid must serve every formula reading the source -- that is what bounds the binary count."""
    fs = [parse_formula("0.98*(x^4)"), parse_formula("-0.3*(x^2)"), parse_formula("0.1*(x^6)")]
    g = build_grid("GDP", 0.0, 1.0, fs, {}, intervals=10)
    for f in fs:
        assert grid_error(g, f, {}) < 0.02
        assert len(sample_at(f, g.breakpoints, {})) == len(g.breakpoints)


def test_value_range_matches_a_known_curve():
    lo, hi = value_range(parse_formula("-0.2+(0.4*x)"), 0.0, 1.0, {})
    assert lo == pytest.approx(-0.2) and hi == pytest.approx(0.2)


def test_bilinear_formula_uses_the_referenced_node():
    f = parse_formula("0.25*(x^5)*Narcotics")
    assert f.refs == frozenset({"Narcotics"})
    assert classify(f, 0.0, 1.0, {"Narcotics": 1.0}) is None
    # the ref is a plain multiplier: doubling it doubles the effect
    a = f.evaluate(0.8, {"Narcotics": 0.4})
    b = f.evaluate(0.8, {"Narcotics": 0.8})
    assert b == pytest.approx(2 * a)


def test_unevaluable_range_is_reported_not_papered_over():
    """A fractional power of a negative base must raise, not silently yield a fabricated number."""
    f = parse_formula("0-(0.44*x)^1.4")
    with pytest.raises(RangeError):
        classify(f, -1.0, 1.0, {})


def test_pwl_interpolation_is_exact_at_breakpoints():
    f = parse_formula("0.7*(x^3)")
    g = build_grid("S", 0.0, 1.0, [f], {}, intervals=5)
    vals = sample_at(f, g.breakpoints, {})
    for b, v in zip(g.breakpoints, vals):
        assert v == pytest.approx(0.7 * b ** 3)
    assert not any(math.isnan(v) for v in vals)
