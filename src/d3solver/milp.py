"""Layer 2, global form: the whole effect network encoded as one mixed-integer program.

The SLP in :mod:`d3solver.optimize` linearizes *around an operating point* and walks downhill from
there, with the situation set frozen. That makes it a local method by construction, and it therefore
cannot answer the question ``notes/scope.md`` puts at the centre of the project -- *can these policies
pull the country out of its current basin?* -- because freezing the situations **is** pinning the basin.

This module takes the other route named in the README: encode the equilibrium itself as constraints
and let a MILP solver search the whole thing at once.

    maximise    sum_n w_n * v_n
    subject to  v_n = clamp(default_n + sum_e contribution_e,  min_n, max_n)   for every node
                balance(p) >= 0
                p_j in [0, 1]

The encoding rests on three facts measured from the shipped data, not assumed:

* **89% of edges are affine** in their source value, so they enter the MILP exactly, for free.
* The nonlinear remainder reads only ~57 distinct source nodes, and a piecewise-linear grid belongs
  to a *source*, not an edge -- so all formulas of the same source share one set of binaries
  (see :mod:`d3solver.pwl`).
* **Situation hysteresis is what makes the model bistable, and a binary is exactly the right variable
  for it.** A situation is a node with a start trigger and a lower stop trigger; at equilibrium the
  self-consistency condition is ``active => value >= stop`` and ``inactive => value <= start``. In the
  band between the two triggers *both* assignments are consistent -- that is the bistability, stated
  as a constraint. The MILP is free to pick either, which is precisely the basin-escape search the SLP
  cannot perform.

**What is approximate, stated plainly.** Piecewise-linear segments approximate the power curves (the
worst per-formula error is reported in :attr:`MilpSolution.max_pwl_error`); the ~13 edges that multiply
by a second node's value are relaxed with McCormick envelopes; and policy cost/income are taken as
linear through the origin with their multiplier factors held at the reference state. All three can make
the MILP's own objective **optimistic**. That is why :attr:`MilpSolution.milp_objective` is a proposal
and a bound, never a result: the caller re-scores the returned policy vector through the exact Layer-1
solver, which remains the arbiter. Propose in the relaxation, verify against the ground truth below it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .budget import AnchoredBudget, raw_cost, raw_income
from .model import GameModel
from .network import build_full_incoming
from .pwl import Affine, Grid, RangeError, build_grid, classify, grid_error, sample_at, value_range

_CONST = "_default_"          # constant-base token; its formulas ignore x (mirrors solver.py)
_VOTER_LO, _VOTER_HI = -1.0, 1.0   # voter-group clamp assumption, same as solver.py


def _san(name: str) -> str:
    """CBC-safe variable name."""
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


@dataclass
class LinearBudget:
    """Policy cost/income as slopes through the origin, in $Bn per unit of slider.

    Through the origin because that is the shape :class:`d3solver.budget.AnchoredBudget` already has
    (``c0 * s / v0``), and because an affine fit with a positive intercept would hand the MILP free
    income at ``s = 0`` -- an artefact it would happily exploit. Exact at ``s = 0`` and ``s = 1``.
    """

    cost_slope: dict[str, float] = field(default_factory=dict)
    income_slope: dict[str, float] = field(default_factory=dict)

    def net_slope(self, name: str) -> float:
        return self.income_slope.get(name, 0.0) - self.cost_slope.get(name, 0.0)


def linear_budget(model: GameModel, ab: AnchoredBudget, csv_cost_k: float, csv_income_k: float,
                  ref_state: Mapping[str, float]) -> LinearBudget:
    """Build the linear budget, mirroring :func:`d3solver.optimize._cost` / ``_income`` at ``s = 1``."""
    lb = LinearBudget()
    for name, pol in model.policies.items():
        if ab.val0.get(name, 0.0) > 1e-9:      # grounded anchor from the save
            lb.cost_slope[name] = ab.cost(name, 1.0)
            lb.income_slope[name] = ab.income(name, 1.0)
        else:                                   # not enacted in the save -> CSV estimate
            lb.cost_slope[name] = raw_cost(pol, 1.0, ref_state) * csv_cost_k
            lb.income_slope[name] = raw_income(pol, 1.0, ref_state) * csv_income_k
    return lb


@dataclass
class MilpSolution:
    settings: dict[str, float]                       # the proposed policy vector
    values: dict[str, float]                         # the MILP's own predicted node values
    active: dict[str, bool]                          # its predicted situation set (the basin it chose)
    milp_objective: float                            # X under the relaxation -- optimistic, see module doc
    milp_balance: float
    status: str
    bound: float | None = None                       # best bound from the solver, if reported
    n_binaries: int = 0
    n_grids: int = 0
    max_pwl_error: float = 0.0
    worst_pwl_formula: str = ""
    problems: list[tuple[str, str, str]] = field(default_factory=list)  # (where, what, why)

    def summary(self) -> str:
        gap = ""
        if self.bound is not None and abs(self.bound) > 1e-9:
            gap = f", bound {self.bound:+.3f} (gap {abs(self.bound - self.milp_objective):.3f})"
        return (f"{self.status}: X_milp={self.milp_objective:+.3f}{gap}, "
                f"balance=${self.milp_balance:+.0f}Bn, {sum(self.active.values())} situations active, "
                f"{self.n_grids} PWL grids / {self.n_binaries} binaries, "
                f"max PWL err {self.max_pwl_error:.2e}, {len(self.problems)} problems")


def _node_meta(model: GameModel) -> dict[str, tuple[float, float, float]]:
    """(default, min, max) per endogenous node -- identical to the set solver.py iterates."""
    meta: dict[str, tuple[float, float, float]] = {}
    for n, sv in model.sim_values.items():
        meta[n] = (sv.default, sv.min, sv.max)
    for n, vt in model.voter_types.items():
        meta[n] = (vt.default, _VOTER_LO, _VOTER_HI)
    for n in model.situations:
        meta[n] = (0.0, 0.0, 1.0)
    return meta


def _product_form(f, lo: float, hi: float, ref_state: Mapping[str, float]) -> str | None:
    """If ``f`` is ``g(x) * ref`` for exactly one referenced node, return that node's name.

    Verified numerically rather than assumed: ``notes/grammar.md`` says refs act as multipliers, and
    this checks that claim against the actual formula before relying on it.
    """
    if len(f.refs) != 1:
        return None
    ref = next(iter(f.refs))
    unit = dict(ref_state)
    unit[ref] = 1.0
    for x in (lo + 0.13 * (hi - lo), lo + 0.61 * (hi - lo), hi):
        try:
            g = f.evaluate(x, unit)
            for r in (0.3, 0.75):
                probe = dict(ref_state)
                probe[ref] = r
                if abs(f.evaluate(x, probe) - g * r) > 1e-9:
                    return None
        except Exception:  # noqa: BLE001
            return None
    return ref


def solve_milp(
    model: GameModel,
    exo: Mapping[str, float],
    weights: Mapping[str, float],
    budget: LinearBudget,
    *,
    ref_state: Mapping[str, float],
    intervals: int = 8,
    balance_min: float | None = 0.0,
    balance_max: float | None = None,
    fixed_policies: Mapping[str, float] | None = None,
    policy_bounds: Mapping[str, tuple[float, float]] | None = None,
    force_active: Mapping[str, bool] | None = None,
    time_limit: float = 300.0,
    gap_rel: float = 0.01,
    msg: int = 0,
) -> MilpSolution:
    """Build and solve the network-wide MILP. See the module docstring for what is exact and what is not.

    ``ref_state`` supplies values for any node a bilinear or cost-multiplier term is held at, and is
    also the fallback for formulas that cannot be evaluated across their full declared range.
    ``force_active`` pins named situations (pass the current set to reproduce the SLP's frozen basin;
    leave it out to let the solver choose, which is the point of this module).
    """
    import pulp

    problems: list[tuple[str, str, str]] = []
    incoming = build_full_incoming(model)
    meta = _node_meta(model)
    situations = set(model.situations)

    prob = pulp.LpProblem("d3_equilibrium", pulp.LpMaximize)

    # ---- decision variables: policy sliders -------------------------------------------------
    pvar: dict[str, object] = {}
    for name in model.policies:
        lo, hi = (policy_bounds or {}).get(name, (0.0, 1.0))
        if fixed_policies and name in fixed_policies:
            lo = hi = float(fixed_policies[name])
        pvar[name] = pulp.LpVariable(f"p_{_san(name)}", lowBound=lo, upBound=hi)

    # ---- state variables: one per endogenous node --------------------------------------------
    vvar: dict[str, object] = {
        n: pulp.LpVariable(f"v_{_san(n)}", lowBound=lo, upBound=hi) for n, (_, lo, hi) in meta.items()
    }
    avar: dict[str, object] = {}
    n_bin = 0
    for n in model.situations:
        if force_active is not None and n in force_active:
            val = 1 if force_active[n] else 0
            avar[n] = pulp.LpVariable(f"a_{_san(n)}", lowBound=val, upBound=val, cat=pulp.LpInteger)
        else:
            avar[n] = pulp.LpVariable(f"a_{_san(n)}", cat=pulp.LpBinary)
            n_bin += 1

    def bounds_of(src: str) -> tuple[float, float] | None:
        """Range of a variable source, or None if the source is fixed/unknown."""
        if src in meta:
            return meta[src][1], meta[src][2]
        if src in pvar:
            return pvar[src].lowBound, pvar[src].upBound
        return None

    def expr_of(src: str):
        return vvar[src] if src in meta else pvar[src]

    # Fixed (non-decision) sources, mirroring solver.py: exogenous globals, the _default_ token, and
    # anything the network references but never defines (reported by the solver as `unresolved`).
    fixed_vals: dict[str, float] = dict(exo)
    fixed_vals[_CONST] = 0.0

    # ---- piecewise-linear grids, one per nonlinear SOURCE -------------------------------------
    nonlinear_by_source: dict[str, list] = {}
    edge_plan: dict[int, tuple] = {}   # id(edge) -> ("affine", src, Affine) | ("pwl", src, f) | ...
    for target, edges in incoming.items():
        if target not in meta:
            continue
        for e in edges:
            b = bounds_of(e.source)
            if b is None:
                continue                       # fixed source -> constant, handled below
            lo, hi = b
            ref = _product_form(e.formula, lo, hi, ref_state) if e.formula.refs else None
            if e.formula.refs and ref is None:
                continue                       # held at reference; recorded when the term is built
            probe = e.formula
            if ref is not None:
                # analyse g(x) = f(x, ref=1); the ref multiplies it back in via McCormick
                unit = dict(ref_state)
                unit[ref] = 1.0
                try:
                    if classify(probe, lo, hi, unit) is None:
                        nonlinear_by_source.setdefault(e.source, []).append((probe, unit))
                except RangeError:
                    pass
                continue
            try:
                if classify(probe, lo, hi, ref_state) is None:
                    nonlinear_by_source.setdefault(e.source, []).append((probe, dict(ref_state)))
            except RangeError:
                pass

    grids: dict[str, Grid] = {}
    max_err, worst_formula = 0.0, ""
    for src, entries in nonlinear_by_source.items():
        lo, hi = bounds_of(src)
        forms = [f for f, _ in entries]
        state_for = entries[0][1]
        try:
            g = build_grid(src, lo, hi, forms, state_for, intervals=intervals)
        except RangeError as exc:
            problems.append((src, "grid", str(exc)))
            continue
        g.deltas = [pulp.LpVariable(f"d_{_san(src)}_{k}", lowBound=0.0, upBound=1.0)
                    for k in range(g.n_intervals)]
        g.zs = [pulp.LpVariable(f"z_{_san(src)}_{k}", cat=pulp.LpBinary)
                for k in range(g.n_intervals - 1)]
        n_bin += len(g.zs)
        for k in range(g.n_intervals - 1):     # d_{k+1} <= z_k <= d_k  (fill left to right)
            prob += g.deltas[k + 1] <= g.zs[k], f"pwlA_{_san(src)}_{k}"
            prob += g.zs[k] <= g.deltas[k], f"pwlB_{_san(src)}_{k}"
        prob += expr_of(src) == g.x_expr(), f"pwlX_{_san(src)}"
        grids[src] = g
        for f, st in entries:
            err = grid_error(g, f, st)
            if err > max_err:
                max_err, worst_formula = err, f"{src}: {f.source}"

    # ---- helper constructors -----------------------------------------------------------------
    aux = [0]

    def newvar(prefix: str, lo: float, hi: float):
        aux[0] += 1
        return pulp.LpVariable(f"{prefix}{aux[0]}", lowBound=lo, upBound=hi)

    def mccormick(u, ulo: float, uhi: float, v, vlo: float, vhi: float, tag: str):
        """Envelope for the product u*v. Exact when either factor is binary-valued."""
        nonlocal prob
        w = newvar("w", min(ulo * vlo, ulo * vhi, uhi * vlo, uhi * vhi),
                   max(ulo * vlo, ulo * vhi, uhi * vlo, uhi * vhi))
        prob += w >= ulo * v + vlo * u - ulo * vlo, f"mcA_{tag}_{aux[0]}"
        prob += w >= uhi * v + vhi * u - uhi * vhi, f"mcB_{tag}_{aux[0]}"
        prob += w <= uhi * v + vlo * u - uhi * vlo, f"mcC_{tag}_{aux[0]}"
        prob += w <= ulo * v + vhi * u - ulo * vhi, f"mcD_{tag}_{aux[0]}"
        return w

    def gate(y, ylo: float, yhi: float, a, tag: str):
        """q = a * y with a binary -- exact big-M product (an inactive situation exerts nothing)."""
        nonlocal prob
        q = newvar("q", min(0.0, ylo), max(0.0, yhi))
        prob += q <= yhi * a, f"gA_{tag}_{aux[0]}"
        prob += q >= ylo * a, f"gB_{tag}_{aux[0]}"
        prob += q <= y - ylo * (1 - a), f"gC_{tag}_{aux[0]}"
        prob += q >= y - yhi * (1 - a), f"gD_{tag}_{aux[0]}"
        return q

    # ---- node equations ----------------------------------------------------------------------
    for n, (default, lo, hi) in meta.items():
        terms = []          # (expr_or_const, term_lo, term_hi)
        const = default
        for e in incoming.get(n, []):
            src, f = e.source, e.formula
            b = bounds_of(src)

            if b is None:                                   # fixed / unresolved source
                x = fixed_vals.get(src, 0.0)                # solver.py defaults unknowns to 0.0
                if src not in fixed_vals:
                    problems.append((n, "unresolved-source", src))
                try:
                    const += f.evaluate(x, ref_state)
                except Exception as exc:                    # noqa: BLE001
                    problems.append((n, "fixed-eval", f"{f.source}: {exc}"))
                continue

            slo, shi = b
            ref = _product_form(f, slo, shi, ref_state) if f.refs else None
            state_for = dict(ref_state)
            if ref is not None:
                state_for[ref] = 1.0
            elif f.refs:
                problems.append((n, "ref-held-at-reference", f.source))

            # value of the (possibly ref-normalised) formula as a function of the source
            try:
                aff = classify(f, slo, shi, state_for)
                flo, fhi = value_range(f, slo, shi, state_for)
            except RangeError as exc:
                problems.append((n, "range", f"{f.source}: {exc}"))
                try:
                    const += f.evaluate(ref_state.get(src, slo), ref_state)
                except Exception:  # noqa: BLE001
                    pass
                continue

            if aff is not None:
                y, ylo, yhi = aff.c0 + aff.c1 * expr_of(src), flo, fhi
            elif src in grids:
                g = grids[src]
                y = g.f_expr(sample_at(f, g.breakpoints, state_for))
                ylo, yhi = flo, fhi
            else:                                            # grid failed to build -> report, hold
                problems.append((n, "no-grid", f.source))
                const += f.evaluate(ref_state.get(src, slo), state_for)
                continue

            if ref is not None:                              # multiply the second node back in
                rb = bounds_of(ref)
                if rb is None:
                    const_ref = float(fixed_vals.get(ref, ref_state.get(ref, 0.0)))
                    y, ylo, yhi = y * const_ref, min(flo * const_ref, fhi * const_ref), \
                        max(flo * const_ref, fhi * const_ref)
                else:
                    yv = newvar("y", ylo, yhi)
                    prob += yv == y, f"yb_{_san(n)}_{aux[0]}"
                    y = mccormick(yv, ylo, yhi, expr_of(ref), rb[0], rb[1], _san(n))
                    prods = [ylo * rb[0], ylo * rb[1], fhi * rb[0], fhi * rb[1]]
                    ylo, yhi = min(prods), max(prods)

            if src in situations:                            # gate by the situation's own binary
                yv = newvar("g", ylo, yhi)
                prob += yv == y, f"gv_{_san(n)}_{aux[0]}"
                y = gate(yv, ylo, yhi, avar[src], _san(n))
                ylo, yhi = min(0.0, ylo), max(0.0, yhi)

            terms.append((y, ylo, yhi))

        zlo = const + sum(t[1] for t in terms)
        zhi = const + sum(t[2] for t in terms)
        zexpr = const + pulp.lpSum(t[0] for t in terms) if terms else const

        # clamp -- with binaries only on the side that can actually bind
        if not terms:
            prob += vvar[n] == min(max(const, lo), hi), f"const_{_san(n)}"
            continue
        need_lo, need_hi = zlo < lo - 1e-9, zhi > hi + 1e-9
        cur = zexpr
        cur_lo, cur_hi = zlo, zhi
        if need_lo:                                          # t = max(z, lo)
            t = newvar("t", max(zlo, lo), max(zhi, lo))
            u = pulp.LpVariable(f"cl_{_san(n)}", cat=pulp.LpBinary)
            n_bin += 1
            prob += t >= cur, f"clA_{_san(n)}"
            prob += t >= lo, f"clB_{_san(n)}"
            prob += t <= cur + (lo - cur_lo) * u, f"clC_{_san(n)}"
            prob += t <= lo + max(0.0, cur_hi - lo) * (1 - u), f"clD_{_san(n)}"
            cur, cur_lo, cur_hi = t, max(zlo, lo), max(zhi, lo)
        if need_hi:                                          # v = min(t, hi)
            w = pulp.LpVariable(f"ch_{_san(n)}", cat=pulp.LpBinary)
            n_bin += 1
            prob += vvar[n] <= cur, f"chA_{_san(n)}"
            prob += vvar[n] <= hi, f"chB_{_san(n)}"
            prob += vvar[n] >= cur - max(0.0, cur_hi - hi) * w, f"chC_{_san(n)}"
            prob += vvar[n] >= hi - max(0.0, hi - cur_lo) * (1 - w), f"chD_{_san(n)}"
        else:
            prob += vvar[n] == cur, f"eq_{_san(n)}"

    # ---- situation hysteresis: the bistability, stated as constraints -------------------------
    for n, sit in model.situations.items():
        # active   => value >= stop_trigger      (it would have switched off below that)
        # inactive => value <= start_trigger     (it would have switched on above that)
        # Between the two triggers both are feasible: that band IS the two basins.
        prob += vvar[n] >= sit.stop_trigger * avar[n], f"hysOn_{_san(n)}"
        prob += vvar[n] <= sit.start_trigger + (1.0 - sit.start_trigger) * avar[n], f"hysOff_{_san(n)}"

    # ---- budget -------------------------------------------------------------------------------
    bal = pulp.lpSum(budget.net_slope(nm) * pvar[nm] for nm in model.policies)
    if balance_min is not None:
        prob += bal >= balance_min, "balance_floor"
    if balance_max is not None:
        prob += bal <= balance_max, "balance_cap"

    # ---- objective ----------------------------------------------------------------------------
    obj_terms = []
    for nm, w in weights.items():
        if nm in vvar:
            obj_terms.append(w * vvar[nm])
        else:
            problems.append(("objective", "unknown-node", nm))
    prob += pulp.lpSum(obj_terms)

    solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=time_limit, gapRel=gap_rel)
    prob.solve(solver)

    def val(v) -> float:
        """Read a solved variable. CBC's presolve eliminates fixed variables and PuLP then reports
        None for them, so fall back to the bound that pinned it -- treating that None as 0.0 would
        silently report an unpinned value for every policy the caller pinned."""
        raw = v.value()
        if raw is not None:
            return float(raw)
        if v.lowBound is not None and v.upBound is not None and v.lowBound == v.upBound:
            return float(v.lowBound)
        return float(v.lowBound if v.lowBound is not None else 0.0)

    status = pulp.LpStatus[prob.status]
    settings = {nm: val(v) for nm, v in pvar.items()}
    values = {nm: val(v) for nm, v in vvar.items()}
    active = {nm: bool(round(val(v))) for nm, v in avar.items()}
    milp_obj = float(pulp.value(prob.objective) or 0.0)
    milp_bal = sum(budget.net_slope(nm) * settings[nm] for nm in model.policies)
    try:
        bound = float(prob.bestBound) if getattr(prob, "bestBound", None) is not None else None
    except (TypeError, ValueError):
        bound = None

    return MilpSolution(
        settings=settings, values=values, active=active,
        milp_objective=milp_obj, milp_balance=milp_bal, status=status, bound=bound,
        n_binaries=n_bin, n_grids=len(grids), max_pwl_error=max_err,
        worst_pwl_formula=worst_formula, problems=problems,
    )


# ---------------------------------------------------------------------------------------------
# Outer loop: re-linearise the budget where the exact solver actually lands
# ---------------------------------------------------------------------------------------------

@dataclass
class RefineRound:
    milp_objective: float
    milp_balance: float
    exact_objective: float
    exact_balance: float
    margin: float
    status: str
    active: int

    def line(self, i: int) -> str:
        return (f"  {i:2d}: milp X={self.milp_objective:+.3f} bal=${self.milp_balance:+5.0f}Bn"
                f"  ->  exact X={self.exact_objective:+.3f} bal=${self.exact_balance:+6.0f}Bn"
                f"  [{self.active} active, margin ${self.margin:.0f}Bn, {self.status}]")


@dataclass
class RefineResult:
    settings: dict[str, float]
    objective: float                 # exact, from Layer 1 -- the number that counts
    balance: float                   # exact
    equilibrium: object              # the Layer-1 Equilibrium of the returned settings
    rounds: list[RefineRound] = field(default_factory=list)
    last: MilpSolution | None = None
    feasible: bool = False


def refine_milp(model: GameModel, exo: Mapping[str, float], weights: Mapping[str, float],
                ab: AnchoredBudget, csv_cost_k: float, csv_income_k: float, *,
                ref_state: Mapping[str, float], ref_active: Mapping[str, bool] | None = None,
                rounds: int = 5, balance_min: float = 0.0, freeze_active: bool = False,
                **milp_kwargs) -> RefineResult:
    """Solve the MILP, verify with Layer 1, re-linearise the budget there, repeat.

    One MILP solve alone is not enough, and the reason is instructive: policy cost and income are
    multiplied by factors that are themselves *endogenous* (dominantly GDP), so a budget linearised at
    the starting state is honest only near that state. Drive GDP somewhere new -- which is exactly what
    a good policy set does -- and every cost in the country moves with it. The first solve of the US
    start proposes a vector the linear budget scores at $0Bn and the exact solver scores at -$899Bn,
    entirely from that effect.

    So the budget gets the same treatment as everything else in this project: propose against a
    linearisation, verify against the oracle, and re-linearise **where the oracle actually landed**.
    ``margin`` is a restoration term -- when the exact solver reports a shortfall, the next MILP is
    required to clear it by that much, and the requirement relaxes once it stops binding.

    The returned solution is the best round **as scored by Layer 1**, never by the MILP's own optimistic
    objective, and ``feasible`` reports whether the exact budget constraint is actually satisfied.
    """
    from .optimize import evaluate, make_objective

    objective = make_objective(weights)
    state: dict[str, float] = dict(ref_state)
    active_seed = dict(ref_active) if ref_active else None
    margin = 0.0
    result = RefineResult(settings={}, objective=float("-inf"), balance=0.0, equilibrium=None)

    for _ in range(rounds):
        lb = linear_budget(model, ab, csv_cost_k, csv_income_k, state)
        sol = solve_milp(model, exo, weights, lb, ref_state=state,
                         balance_min=balance_min + margin,
                         force_active=active_seed if freeze_active else None, **milp_kwargs)
        exact_obj, exact_bal, eq = evaluate(model, sol.settings, exo, objective, ab,
                                            csv_cost_k, csv_income_k,
                                            sol.values, sol.active, False)
        result.rounds.append(RefineRound(
            milp_objective=sol.milp_objective, milp_balance=sol.milp_balance,
            exact_objective=exact_obj, exact_balance=exact_bal, margin=margin,
            status=sol.status, active=sum(eq.active.values()),
        ))
        result.last = sol

        feasible = exact_bal >= balance_min
        if feasible and exact_obj > result.objective:
            result.settings, result.objective = dict(sol.settings), exact_obj
            result.balance, result.equilibrium, result.feasible = exact_bal, eq, True
        elif not result.feasible and exact_obj > result.objective:
            # nothing feasible yet -- keep the best-so-far so the caller always gets something back
            result.settings, result.objective = dict(sol.settings), exact_obj
            result.balance, result.equilibrium = exact_bal, eq

        if exact_bal < balance_min:
            margin += (balance_min - exact_bal)     # the oracle says short -- demand that much more
        else:
            margin *= 0.5                           # it stopped binding; ease off
        state = dict(eq.values)                     # re-linearise where the oracle actually landed

    return result


__all__ = ["LinearBudget", "MilpSolution", "RefineResult", "RefineRound",
           "linear_budget", "refine_milp", "solve_milp"]
