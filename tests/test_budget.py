"""Tests for the budget layer's multiplier grammar.

The `_default_` rule is load-bearing: `notes/grammar.md` calls it a constant *base* term, and treating
it as another factor inverts the sign of every multiplier that uses one — which silently produced
negative costs for the four largest US programmes and forced the whole budget onto savegame anchors.
"""

from __future__ import annotations

import pytest

from d3solver.budget import _multiplier_value


def test_default_is_an_additive_base_not_a_factor():
    # _default_,1.0 with a factor evaluating to -0.048 must give 0.952, not -0.048.
    v = _multiplier_value("_default_,1.0;Wages,-0.1+(0.2*x)", 0.88, {"Wages": 0.2609})
    assert v == pytest.approx(1.0 + (-0.1 + 0.2 * 0.2609))
    assert v > 0.9


def test_a_zero_valued_factor_cannot_zero_the_whole_multiplier():
    # State Pensions: '_default_,1.0;Health,0.2*(x^6)' at Health=0 must stay 1.0, not collapse to 0.
    v = _multiplier_value("_default_,1.0;Health,0.2*(x^6)", 0.51, {"Health": 0.0})
    assert v == pytest.approx(1.0)


def test_without_a_default_the_factors_multiply():
    v = _multiplier_value("GDP,0.5+(0.5*x);TaxEvasion,1.0-(0.2*x)", 0.4,
                          {"GDP": 0.6, "TaxEvasion": 0.5})
    assert v == pytest.approx((0.5 + 0.5 * 0.6) * (1.0 - 0.2 * 0.5))


def test_an_unknown_factor_falls_back_to_the_setting():
    # Poor_perc is never defined by the network; the setting stands in for it (and is why Food Stamps
    # is the one policy that misses the common CSV->$ constant).
    v = _multiplier_value("Poor_perc,0+(1.0*x)", 0.82, {})
    assert v == pytest.approx(0.82)


def test_empty_multiplier_is_neutral():
    assert _multiplier_value("", 0.5, {}) == pytest.approx(1.0)
