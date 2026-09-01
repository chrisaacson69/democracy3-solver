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


# --- state elasticity: the anchored budget must feel the economy -----------------------------

def _ab(**kw):
    from d3solver.budget import AnchoredBudget
    base = dict(cost0={"Tax": 100.0}, income0={"Tax": 100.0}, val0={"Tax": 0.5},
                income_mult={"Tax": "GDP,0.5+(0.5*x)"}, cost_mult={},
                anchor_state={"GDP": 0.6})
    base.update(kw)
    return AnchoredBudget(**base)


def test_elasticity_is_exactly_one_at_the_anchor_state():
    """The whole point of the anchor-relative form: nothing moves where it was calibrated."""
    ab = _ab()
    assert ab.income("Tax", 0.5, {"GDP": 0.6}) == pytest.approx(ab.income("Tax", 0.5, None))


def test_revenue_falls_when_the_economy_does():
    ab = _ab()
    healthy = ab.income("Tax", 0.5, {"GDP": 0.6})
    dead = ab.income("Tax", 0.5, {"GDP": 0.0})
    assert dead < healthy
    # GDP,0.5+(0.5*x): 0.5 at GDP=0 against 0.8 at GDP=0.6
    assert dead == pytest.approx(healthy * (0.5 / 0.8))


def test_without_an_anchor_state_the_budget_is_blind_as_before():
    """Old callers must not silently change behaviour."""
    ab = _ab(anchor_state={})
    assert ab.income("Tax", 0.5, {"GDP": 0.0}) == pytest.approx(ab.income("Tax", 0.5, None))


def test_a_collapsed_multiplier_yields_no_flow_rather_than_negative_flow():
    # anchor multiplier is +0.4 (a usable reference); at GDP=0.1 it goes to -0.4, which must read as
    # "no revenue", never as negative revenue.
    ab = _ab(income_mult={"Tax": "GDP,-0.5+(1.0*x)"}, anchor_state={"GDP": 0.9})
    assert ab.income("Tax", 0.5, {"GDP": 0.9}) > 0.0
    assert ab.income("Tax", 0.5, {"GDP": 0.1}) == pytest.approx(0.0)


def test_an_unusable_reference_falls_back_to_the_anchored_level():
    """If the multiplier is non-positive at the anchor there is no ratio to form; keep the level."""
    ab = _ab(income_mult={"Tax": "GDP,-1.0+(1.0*x)"}, anchor_state={"GDP": 0.9})
    assert ab.income("Tax", 0.5, {"GDP": 0.1}) == pytest.approx(ab.income("Tax", 0.5, None))


def test_elasticity_is_capped():
    ab = _ab(income_mult={"Tax": "GDP,0.001+(1.0*x)"}, anchor_state={"GDP": 0.0})
    huge = ab.income("Tax", 0.5, {"GDP": 1.0})
    assert huge <= ab.income("Tax", 0.5, None) * ab.max_elasticity + 1e-9
