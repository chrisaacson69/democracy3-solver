"""Scenario construction — the exogenous inputs a solve is run against.

This exists because the same seven-line block was copy-pasted into every driver script, and one of its
lines quietly contradicted the project's own scope decision for as long as it existed.

``notes/scope.md`` (Addendum 2026-08-10) fixes the semantics: we compute a **counterfactual
equilibrium** with policies fully implemented and the world economy sitting at its long-run
**average**, and the boom/bust cycle is absorbed by savings rather than modelled turn by turn. The
scripts, however, all read ``save.globals["globaleconomy_pos"]`` with ``0.5`` as a *fallback* — and
that key is present in every save, so the fallback never fired. Every result this project has produced
was computed at the save's momentary cycle position (0.3113 for the US start: a below-average economy),
not at the average.

The fix is not to hardcode ``0.5`` in seven places. Scope.md also says the economy position is
**"sweepable for good/bad times"**, so the honest shape is one parameter with the average as its
default, which is what :func:`from_savegame` provides and what ``scripts/economy_sweep.py`` sweeps.

.. warning::
   ``_year`` is knowingly left as it was found: it is fed ``save.globals["globaleconomy_years"]``,
   which is ``8.0`` — exactly ``GLOBAL_ECONOMY_CYCLE_LENGTH_YEARS`` from the game's
   ``data/simconfig.txt``. That is the cycle *length*, not elapsed time, and every other node in this
   model is normalised to [0,1], so 8.0 is an order of magnitude out of range. It drives
   ``_Terrorism +0.08`` and ``OilSupply -0.12``. We do **not** guess a replacement — what the engine
   actually passes for ``_year`` is unresolved, and it is recorded as an open mechanic in
   ``notes/scope.md``. Pass ``year=`` explicitly to experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .savegame import SaveState

#: The world economy's long-run average position, per notes/scope.md. Its range is [0, 1].
AVERAGE_ECONOMY = 0.5


@dataclass
class Scenario:
    """Everything a solve needs besides the model itself."""

    policies: dict[str, float]                       # the starting policy vector
    exogenous: dict[str, float]                      # inputs the solve reads but never updates
    ref_state: dict[str, float]                      # reference node values (warm start / linearisation)
    ref_active: dict[str, bool]                      # the save's situation set
    economy: float = AVERAGE_ECONOMY                 # the world-economy position this scenario uses
    notes: list[str] = field(default_factory=list)   # anything the caller should know it inherited

    def with_economy(self, economy: float) -> "Scenario":
        """The same scenario at a different point in the world-economy cycle."""
        exo = dict(self.exogenous)
        exo["_globaleconomy_"] = float(economy)
        return Scenario(policies=dict(self.policies), exogenous=exo,
                        ref_state=dict(self.ref_state), ref_active=dict(self.ref_active),
                        economy=float(economy), notes=list(self.notes))


def save_economy(save: SaveState) -> float:
    """The world-economy position the save was actually sitting at — the as-played cycle point.

    Use this to reproduce a specific moment of a playthrough. It is *not* the default, because the
    scope decision optimizes the average-economy equilibrium, not one arbitrary point of the cycle.
    """
    return float(save.globals.get("globaleconomy_pos", AVERAGE_ECONOMY))


def from_savegame(save: SaveState, *, economy: float | None = None,
                  year: float | None = None) -> Scenario:
    """Build a :class:`Scenario` from a parsed savegame.

    ``economy`` defaults to :data:`AVERAGE_ECONOMY` — the scope decision — rather than to the save's
    momentary position. Pass ``economy=save_economy(save)`` to reproduce the as-played state.
    ``year`` defaults to the value the scripts have always used; see the module warning.
    """
    eco = AVERAGE_ECONOMY if economy is None else float(economy)
    yr = float(save.globals.get("globaleconomy_years", 0.0)) if year is None else float(year)

    exogenous = {
        "_global_socialism": save.globals.get("socialism", 0.5),
        "_global_liberalism": save.globals.get("liberalism", 0.5),
        "_globaleconomy_": eco,
        "_year": yr,
    }
    ref_state = dict(save.sim_values)
    ref_state.update({n: (d["val"] if d["active"] else 0.0) for n, d in save.situations.items()})

    notes: list[str] = []
    played = save_economy(save)
    if abs(played - eco) > 1e-9:
        notes.append(f"economy pinned at {eco:.4f} (scope: the long-run average); "
                     f"the save was played at {played:.4f}")
    if yr != 0.0:
        notes.append(f"_year={yr:g} inherited unchanged and is suspect — "
                     f"it is the simconfig cycle LENGTH, not elapsed time (see notes/scope.md)")

    return Scenario(
        policies={n: d["val"] for n, d in save.policies.items()},
        exogenous=exogenous,
        ref_state=ref_state,
        ref_active={n: bool(d["active"]) for n, d in save.situations.items()},
        economy=eco,
        notes=notes,
    )


__all__ = ["AVERAGE_ECONOMY", "Scenario", "from_savegame", "save_economy"]
