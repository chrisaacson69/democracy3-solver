"""Tests for the effect-formula parser/evaluator."""

from __future__ import annotations

import math

import pytest

from d3solver.formula import FormulaError, parse_formula


def test_linear():
    f = parse_formula("-0.2+(0.4*x)")
    assert f.evaluate(0.0) == pytest.approx(-0.2)
    assert f.evaluate(1.0) == pytest.approx(0.2)
    assert f.refs == frozenset()


def test_power_caret():
    f = parse_formula("0.98*(x^4)")
    assert f.evaluate(0.5) == pytest.approx(0.98 * 0.5**4)


def test_fractional_power():
    f = parse_formula("0.30*(x^0.6)+0.07")
    assert f.evaluate(0.5) == pytest.approx(0.30 * 0.5**0.6 + 0.07)


def test_leading_paren_and_add():
    f = parse_formula("(0.025+0.035*x)")
    assert f.evaluate(1.0) == pytest.approx(0.06)


def test_state_reference():
    f = parse_formula("0.25*(x^5)*Narcotics")
    assert f.refs == frozenset({"Narcotics"})
    assert f.evaluate(1.0, {"Narcotics": 0.5}) == pytest.approx(0.125)


def test_missing_state_raises():
    f = parse_formula("0.1*Foo")
    with pytest.raises(FormulaError):
        f.evaluate(1.0)  # no state provided
    with pytest.raises(FormulaError):
        f.evaluate(1.0, {})  # ref not present


@pytest.mark.parametrize("bad", ["", "0.0.5+(0.15*x)", "0+0.10*x)", "-0.1*(x^2))"])
def test_shipped_typos_rejected(bad):
    """The malformed formulas shipped in the game CSVs must raise, not silently evaluate."""
    with pytest.raises(FormulaError):
        parse_formula(bad)


def test_no_builtins_leak():
    # Names resolve only from state; there is no way to call functions.
    with pytest.raises(FormulaError):
        parse_formula("pow(x,2)")  # Call node is disallowed
