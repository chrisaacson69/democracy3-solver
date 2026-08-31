"""Rough endogenous budget model.

Deliberately approximate (per project steer: the efficient frontier emerges from a rough estimate — we
do NOT chase exact dollar fidelity). Each policy's cost and each tax's income scale with the slider
setting and a few multiplier factors (dominant one: GDP). Because the CSV's ``maxincome`` and
``maxcost`` are in *different* internal units (income figures dwarf cost figures), we don't subtract raw
values; instead we calibrate one global scale per side against a known state (the US save's screenshot
totals) so ``balance`` is meaningful. Two-parameter calibration, one anchor point — rough on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .formula import Formula, parse_formula
from .model import GameModel, Policy


def _parse_multiplier(spec: str) -> list[tuple[str, Formula]]:
    """Parse a ';'-separated 'Factor,formula' list (income/cost multiplier)."""
    out: list[tuple[str, Formula]] = []
    for part in (spec or "").split(";"):
        part = part.strip()
        if not part or "," not in part:
            continue
        factor, _, fexpr = part.partition(",")
        try:
            out.append((factor.strip(), parse_formula(fexpr)))
        except Exception:
            continue
    return out


_DEFAULT_FACTOR = "_default_"


def _multiplier_value(spec: str, setting: float, state: Mapping[str, float]) -> float:
    """Evaluate a ``Factor,formula`` multiplier list.

    ``notes/grammar.md``: **"``_default_,k`` sets a constant base term"** — a base the other factors
    adjust, not another thing to multiply by. Treating it as a factor is not a rounding error, it
    inverts the sign: ``_default_,1.0;Wages,-0.1+(0.2*x)`` at Wages=0.26 is ``1.0 + (-0.048) = 0.95``,
    but multiplying gives ``-0.048``. That made Military Spending, State Pensions, State Schools and
    Police Force evaluate to a *negative or zero* cost, which is why the CSV cost path was unusable
    and everything had to be anchored to a savegame instead.

    With the base handled correctly, 31 of the 32 enacted policies agree on a single CSV→$ conversion
    constant to within ±11% (median 0.0265 in the save's calibrated frame). The lone holdout is Food
    Stamps, whose multiplier reads ``Poor_perc`` — one of the ``*_perc`` membership values the network
    never defines, so ``state.get`` falls back to the policy setting. Resolving those would close the
    last gap and let the budget be grounded in the CSVs alone.

    x for each non-default factor is its node value, else the setting (a rough proxy — e.g. TaxEvasion,
    which we don't solve, scales with the tax rate).
    """
    base: float | None = None
    others: list[float] = []
    for factor, f in _parse_multiplier(spec):
        if factor == _DEFAULT_FACTOR:
            try:
                base = f.evaluate(0.0, state)   # a constant; its formula ignores x
            except Exception:
                pass
            continue
        x = float(state.get(factor, setting))
        try:
            others.append(f.evaluate(x, state))
        except Exception:
            pass
    if base is not None:
        return base + sum(others)
    prod = 1.0
    for v in others:
        prod *= v
    return prod


def raw_cost(p: Policy, setting: float, state: Mapping[str, float]) -> float:
    if setting <= 0:
        return 0.0
    base = p.mincost + (p.maxcost - p.mincost) * setting
    return base * _multiplier_value(p.cost_multiplier, setting, state)


def raw_income(p: Policy, setting: float, state: Mapping[str, float]) -> float:
    if setting <= 0 or p.maxincome <= 0:
        return 0.0
    base = p.minincome + (p.maxincome - p.minincome) * setting
    return base * _multiplier_value(p.income_multiplier, setting, state)


@dataclass
class BudgetScale:
    """Global calibration: internal units -> $Bn, separately for income and cost."""
    income_k: float = 1.0
    cost_k: float = 1.0


def raw_totals(model: GameModel, settings: Mapping[str, float],
               state: Mapping[str, float]) -> tuple[float, float]:
    inc = sum(raw_income(p, settings.get(n, 0.0), state) for n, p in model.policies.items())
    cost = sum(raw_cost(p, settings.get(n, 0.0), state) for n, p in model.policies.items())
    return inc, cost


def calibrate(model: GameModel, settings: Mapping[str, float], state: Mapping[str, float],
              income_target: float, expenditure_target: float) -> BudgetScale:
    """Pick income/cost scales so totals match known $ figures at this anchor state."""
    inc, cost = raw_totals(model, settings, state)
    return BudgetScale(
        income_k=(income_target / inc) if inc else 1.0,
        cost_k=(expenditure_target / cost) if cost else 1.0,
    )


def balance(model: GameModel, settings: Mapping[str, float], state: Mapping[str, float],
            scale: BudgetScale) -> dict[str, float]:
    inc, cost = raw_totals(model, settings, state)
    income_bn = inc * scale.income_k
    cost_bn = cost * scale.cost_k
    return {"income": income_bn, "expenditure": cost_bn, "balance": income_bn - cost_bn}


@dataclass
class AnchoredBudget:
    """Per-policy cost/income anchored to the save's real $ figures, scaled linearly with the setting.

    cost(n, s)   = cost0[n]   * (s / val0[n]) * income/cost global factor
    Rankings come from the grounded anchors; two global factors pin the absolute totals to known $
    (absorbing non-policy items like debt interest). Rough by design.
    """
    cost0: dict[str, float]      # $Bn at val0
    income0: dict[str, float]
    val0: dict[str, float]
    cost_k: float = 1.0
    income_k: float = 1.0

    def cost(self, name: str, setting: float) -> float:
        v0, c0 = self.val0.get(name, 0.0), self.cost0.get(name, 0.0)
        if v0 <= 1e-9 or c0 <= 0.0:
            return 0.0
        return c0 * (setting / v0) * self.cost_k

    def income(self, name: str, setting: float) -> float:
        v0, i0 = self.val0.get(name, 0.0), self.income0.get(name, 0.0)
        if v0 <= 1e-9 or i0 <= 0.0:
            return 0.0
        return i0 * (setting / v0) * self.income_k

    def balance(self, settings: Mapping[str, float]) -> dict[str, float]:
        inc = sum(self.income(n, s) for n, s in settings.items())
        cost = sum(self.cost(n, s) for n, s in settings.items())
        return {"income": inc, "expenditure": cost, "balance": inc - cost}


def anchored_from_save(save, income_target: float, expenditure_target: float,
                       unit: float = 1000.0) -> AnchoredBudget:
    """Build an AnchoredBudget from a SaveState, calibrated so totals hit the $ targets."""
    cost0 = {n: d["cost"] / unit for n, d in save.policies.items()}
    income0 = {n: d["income"] / unit for n, d in save.policies.items()}
    val0 = {n: d["val"] for n, d in save.policies.items()}
    tot_c, tot_i = sum(cost0.values()), sum(income0.values())
    return AnchoredBudget(
        cost0=cost0, income0=income0, val0=val0,
        cost_k=(expenditure_target / tot_c) if tot_c else 1.0,
        income_k=(income_target / tot_i) if tot_i else 1.0,
    )


__all__ = ["BudgetScale", "AnchoredBudget", "anchored_from_save",
           "raw_cost", "raw_income", "raw_totals", "calibrate", "balance"]
