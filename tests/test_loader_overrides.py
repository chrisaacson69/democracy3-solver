"""Mission overrides: the network is shared across countries, the edits are not.

A single `data/simulation/` serves all six countries, so loading the CSVs alone gives a model that is
*generic* but, for any specific country, quietly wrong. The USA deletes `HandgunLaws ->
ViolentCrimeRate` and adds two tax edges onto `MiddleIncome`; loading only the shared CSVs has handgun
laws cutting violent crime in a US game whose own scenario says they do not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from d3solver import load_model
from d3solver.config import sim_dir
from d3solver.loader import load_country, load_overrides
from d3solver.model import Effect, GameModel, Policy, SimValue
from d3solver.formula import parse_formula


def _tiny(tmp_path: Path):
    m = GameModel()
    m.policies["Guns"] = Policy(name="Guns", guiname="Guns", slider="", description="", flags=[],
                                department="", mincost=0, maxcost=0, cost_multiplier="",
                                implementation=0, minincome=0, maxincome=0, income_multiplier="",
                                effects=[Effect("Crime", parse_formula("0.2-(0.4*x)"))])
    m.sim_values["Crime"] = SimValue(name="Crime", guiname="Crime", description="", zone="",
                                     default=0.5, min=0.0, max=1.0, emotion="HIGHBAD")
    d = tmp_path / "overrides"; d.mkdir()
    return m, d


def test_delete_removes_the_edge(tmp_path):
    m, d = _tiny(tmp_path)
    (d / "x.ini").write_text('[override]\nHostName = "Guns"\nTargetName = "Crime"\n'
                             'Equation = "DELETE"\nInertia = 0\n', encoding="latin-1")
    applied = load_overrides(tmp_path, m)
    assert applied == [("Guns", "Crime", "DELETE")]
    assert not [e for e in m.policies["Guns"].effects if e.target == "Crime"]


def test_an_equation_replaces_in_place(tmp_path):
    m, d = _tiny(tmp_path)
    (d / "x.ini").write_text('[override]\nHostName = "Guns"\nTargetName = "Crime"\n'
                             'Equation = "-0.9*(x^2)"\nInertia = 0\n', encoding="latin-1")
    load_overrides(tmp_path, m)
    got = [e.formula.source for e in m.policies["Guns"].effects if e.target == "Crime"]
    assert got == ["-0.9*(x^2)"]


def test_an_override_for_a_missing_edge_adds_it(tmp_path):
    m, d = _tiny(tmp_path)
    (d / "x.ini").write_text('[override]\nHostName = "Guns"\nTargetName = "Newtarget"\n'
                             'Equation = "0.5*x"\nInertia = 0\n', encoding="latin-1")
    applied = load_overrides(tmp_path, m)
    assert applied and applied[0][2] == "add"


def test_a_malformed_equation_is_reported_not_applied(tmp_path):
    """France ships `0-(0.8*x))` with an unmatched paren. Surface it; never fabricate a value."""
    m, d = _tiny(tmp_path)
    (d / "x.ini").write_text('[override]\nHostName = "Guns"\nTargetName = "Crime"\n'
                             'Equation = "0-(0.8*x))"\nInertia = 0\n', encoding="latin-1")
    load_overrides(tmp_path, m)
    assert any(p[1] == "override" for p in m.problems)
    assert [e.formula.source for e in m.policies["Guns"].effects if e.target == "Crime"] \
        == ["0.2-(0.4*x)"], "the original edge must survive an unparseable override"


def test_no_overrides_directory_is_not_an_error(tmp_path):
    m, _ = _tiny(tmp_path)
    assert load_overrides(tmp_path / "nope", m) == []


@pytest.mark.skipif(not Path(sim_dir()).is_dir(), reason="needs the game data")
def test_the_usa_deletes_the_handgun_edge():
    plain = load_model(sim_dir())
    assert [e for e in plain.policies["HandgunLaws"].effects if e.target == "ViolentCrimeRate"], \
        "the shared CSVs do carry the edge"
    usa, applied = load_country(sim_dir(), "usa")
    assert len(applied) == 3
    assert not [e for e in usa.policies["HandgunLaws"].effects if e.target == "ViolentCrimeRate"]
