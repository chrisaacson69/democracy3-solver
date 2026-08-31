"""Tests for the MILP encoding of the equilibrium.

The MILP is a second implementation of the same fixed point the iterative solver computes, so the
governing test is **agreement**: pin the policy vector and the two must land on the same state, up to
the piecewise-linear tolerance. Anything else the MILP claims is worthless if that fails.

The second group of tests covers the encoding's reason for existing -- the situation binaries. A
situation sitting inside its hysteresis band is consistent both switched on and switched off, and the
MILP must be free to choose, because that choice is the basin.
"""

from __future__ import annotations

import pytest

from d3solver.formula import parse_formula
from d3solver.milp import LinearBudget, solve_milp
from d3solver.model import Effect, GameModel, Policy, SimValue, Situation
from d3solver.solver import solve_equilibrium


def _policy(name: str, effects: list[Effect]) -> Policy:
    return Policy(name=name, guiname=name, slider="none", description="", flags=[], department="",
                  mincost=0.0, maxcost=0.0, cost_multiplier="", implementation=0,
                  minincome=0.0, maxincome=0.0, income_multiplier="", effects=effects)


def _sim(name: str, default: float, lo: float, hi: float, outputs: list[Effect]) -> SimValue:
    return SimValue(name=name, guiname=name, description="", zone="", default=default,
                    min=lo, max=hi, emotion="UNKNOWN", inputs=[], outputs=outputs)


def _model(*, c_max: float = 1.0, with_situation: bool = False) -> GameModel:
    """A: driven by the policy. B: a power of A (exercises the PWL path). C: exercises the clamp."""
    m = GameModel()
    m.policies["Tax"] = _policy("Tax", [Effect("A", parse_formula("0.5*x"))])
    m.sim_values["A"] = _sim("A", 0.1, 0.0, 1.0, [
        Effect("B", parse_formula("0.4*(x^2)")),
        Effect("C", parse_formula("1.0*x")),
    ])
    m.sim_values["B"] = _sim("B", 0.2, 0.0, 1.0, [])
    m.sim_values["C"] = _sim("C", 0.2, 0.0, c_max, [])
    if with_situation:
        # value = 1.25*A, so A=0.4 puts it at 0.5 -- inside the [stop=0.4, start=0.6] band
        m.situations["S"] = Situation(
            name="S", guiname="S", start_trigger=0.6, stop_trigger=0.4, positive=False,
            inputs=[Effect("A", parse_formula("1.25*x"))],
            outputs=[Effect("B", parse_formula("0.3*x"))],
        )
    return m


REF = {"A": 0.4, "B": 0.3, "C": 0.3, "S": 0.5}


def _milp(model, setting, **kw):
    return solve_milp(model, {}, kw.pop("weights", {"B": 1.0}), LinearBudget(),
                      ref_state=REF, fixed_policies={"Tax": setting},
                      balance_min=None, intervals=kw.pop("intervals", 12),
                      time_limit=60, gap_rel=0.0, **kw)


def test_milp_reproduces_the_hand_computed_fixed_point():
    sol = _milp(_model(), 0.6)
    assert sol.status == "Optimal"
    assert sol.values["A"] == pytest.approx(0.4, abs=1e-6)          # 0.1 + 0.5*0.6
    assert sol.values["B"] == pytest.approx(0.264, abs=0.01)        # 0.2 + 0.4*0.4^2


@pytest.mark.parametrize("setting", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_milp_agrees_with_the_iterative_solver(setting):
    """The governing test: two independent implementations of one fixed point must coincide."""
    model = _model()
    sol = _milp(model, setting)
    eq = solve_equilibrium(model, {"Tax": setting}, {})
    for node in ("A", "B", "C"):
        assert sol.values[node] == pytest.approx(eq.values[node], abs=0.01), node


def test_clamp_binds_and_matches_the_solver():
    """C would settle at 0.6 but is capped at 0.3 -- the clamp binaries must reproduce that."""
    model = _model(c_max=0.3)
    sol = _milp(model, 0.6, weights={"C": 1.0})
    eq = solve_equilibrium(model, {"Tax": 0.6}, {})
    assert eq.values["C"] == pytest.approx(0.3, abs=1e-6)
    assert sol.values["C"] == pytest.approx(0.3, abs=1e-6)


def test_situation_in_the_hysteresis_band_can_be_switched_either_way():
    """The bistability, as a test: one state, two self-consistent basins, and the MILP picks."""
    model = _model(with_situation=True)

    on = _milp(model, 0.6, weights={"B": 1.0})            # reward B -> want the situation active
    off = _milp(model, 0.6, weights={"B": -1.0})          # penalise B -> want it inactive
    assert on.active["S"] is True
    assert off.active["S"] is False
    # active adds 0.3 * 0.5 = 0.15 on top of the 0.264 base
    assert on.values["B"] == pytest.approx(0.414, abs=0.01)
    assert off.values["B"] == pytest.approx(0.264, abs=0.01)
    assert on.values["B"] > off.values["B"]


@pytest.mark.parametrize("active", [True, False])
def test_forced_basin_matches_the_frozen_solver(active):
    """Pinning the situations must reproduce exactly what freeze_active gives the iterative solver."""
    model = _model(with_situation=True)
    sol = _milp(model, 0.6, weights={"B": 1.0}, force_active={"S": active})
    eq = solve_equilibrium(model, {"Tax": 0.6}, {},
                           init_values=dict(REF), init_active={"S": active}, freeze_active=True)
    assert sol.active["S"] is active
    assert sol.values["B"] == pytest.approx(eq.values["B"], abs=0.01)


def test_pinned_policy_is_respected():
    sol = _milp(_model(), 0.35)
    assert sol.settings["Tax"] == pytest.approx(0.35, abs=1e-6)


def test_binaries_scale_with_nonlinear_sources_not_edges():
    """A reports the only nonlinear formula, so exactly one grid should be built."""
    sol = _milp(_model(), 0.6)
    assert sol.n_grids == 1
    assert sol.max_pwl_error < 0.01


def test_objective_naming_an_unknown_node_is_reported():
    sol = _milp(_model(), 0.6, weights={"NoSuchNode": 1.0})
    assert any(what == "unknown-node" for _, what, _why in sol.problems)
