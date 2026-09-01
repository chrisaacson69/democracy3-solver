"""First optimizer pass: marginal efficient-frontier analysis.

Couples the equilibrium solver + budget. For each policy we perturb its setting, re-solve the
equilibrium, and measure the change in the objective X and in the budget balance. Ranking moves by
"objective gain per £ spent" (or "£ freed per objective lost") is the efficient frontier / shadow-price
view — the same return-per-£ reasoning an expert uses by eye. Objective is a pluggable weight dict over
outcome nodes (signed: negative weight for HIGHBAD outcomes we want low).

Deliberately rough (per project steer): the frontier ranking is robust to modeling noise.
"""

from __future__ import annotations

from typing import Callable, Mapping

from .budget import AnchoredBudget, raw_cost, raw_income
from .model import GameModel
from .solver import solve_equilibrium


def make_objective(weights: Mapping[str, float]) -> Callable[[Mapping[str, float]], float]:
    return lambda values: sum(w * values.get(n, 0.0) for n, w in weights.items())


def _cost(name, setting, ab, model, state, csv_cost_k):
    if ab.val0.get(name, 0.0) > 1e-9:          # active in save -> grounded anchor
        return ab.cost(name, setting, state)
    return raw_cost(model.policies[name], setting, state) * csv_cost_k   # inactive -> CSV estimate


def _income(name, setting, ab, model, state, csv_income_k):
    if ab.val0.get(name, 0.0) > 1e-9:
        return ab.income(name, setting, state)
    return raw_income(model.policies[name], setting, state) * csv_income_k


def evaluate(model, settings, exo, objective, ab, csv_cost_k, csv_income_k,
             init_values=None, init_active=None, freeze_active=False):
    eq = solve_equilibrium(model, settings, exo, init_values=init_values, init_active=init_active,
                           freeze_active=freeze_active)
    obj = objective(eq.values)
    inc = sum(_income(n, s, ab, model, eq.values, csv_income_k) for n, s in settings.items())
    cost = sum(_cost(n, s, ab, model, eq.values, csv_cost_k) for n, s in settings.items())
    return obj, inc - cost, eq


def marginal_analysis(model, base_settings, exo, objective, ab, csv_cost_k, csv_income_k,
                      *, step=0.1, init_values=None, init_active=None, policies=None,
                      freeze_active=False):
    base_obj, base_bal, _ = evaluate(model, base_settings, exo, objective, ab,
                                     csv_cost_k, csv_income_k, init_values, init_active, freeze_active)
    rows = []
    for n in (policies or model.policies):
        s = base_settings.get(n, 0.0)
        for label, new in (("+", min(1.0, s + step)), ("-", max(0.0, s - step))):
            if abs(new - s) < 1e-9:
                continue
            st = dict(base_settings); st[n] = new
            o, b, _ = evaluate(model, st, exo, objective, ab, csv_cost_k, csv_income_k,
                               init_values, init_active, freeze_active)
            rows.append({"policy": n, "dir": label, "d_obj": o - base_obj, "d_bal": b - base_bal})
    return base_obj, base_bal, rows


def rank_moves(rows, eps=1e-6):
    """Classify moves into three interpretable buckets (avoids degenerate per-£ ratios):

    free_wins  : improve X *and* the budget (dX>0, d_bal>0)          -> sort by dX
    paid_buys  : improve X but cost money   (dX>0, d_bal<0)          -> sort by X per £ spent
    savings    : free money at an X cost     (d_bal>0, dX<0)          -> sort by £ freed per X lost
    """
    free_wins, paid_buys, savings = [], [], []
    for r in rows:
        dO, dB = r["d_obj"], r["d_bal"]
        if dO > eps and dB > eps:
            free_wins.append(r)
        elif dO > eps and dB < -eps:
            paid_buys.append({**r, "x_per_pound": dO / (-dB)})
        elif dB > eps and dO < -eps:
            savings.append({**r, "pound_per_xloss": dB / (-dO)})
    free_wins.sort(key=lambda r: r["d_obj"], reverse=True)
    paid_buys.sort(key=lambda r: r["x_per_pound"], reverse=True)
    savings.sort(key=lambda r: r["pound_per_xloss"], reverse=True)
    return free_wins, paid_buys, savings


def greedy_optimize(model, settings0, exo, objective, ab, csv_cost_k, csv_income_k, *,
                    init_values=None, init_active=None, freeze_active=True,
                    step=0.15, max_moves=40, policies=None):
    """Hill-climb a recommended policy set.

    While in deficit, prefer moves that improve the balance (best if they also improve X); once
    balance>=0, take the move with the largest objective gain that keeps balance>=0. Stops when no
    feasible improving move remains. Rough coordinate ascent — the recommended *set* is what we compare
    to expert play, not exact convergence.
    """
    settings = dict(settings0)
    history = []
    ev = lambda st: evaluate(model, st, exo, objective, ab, csv_cost_k, csv_income_k,
                             init_values, init_active, freeze_active)
    for _ in range(max_moves):
        base_obj, base_bal, rows = marginal_analysis(
            model, settings, exo, objective, ab, csv_cost_k, csv_income_k,
            step=step, init_values=init_values, init_active=init_active,
            freeze_active=freeze_active, policies=policies)
        best = None
        for r in rows:
            new_bal = base_bal + r["d_bal"]
            if base_bal < 0:                          # deficit: must move balance up
                if r["d_bal"] <= 1e-6:
                    continue
                score = (1.0, r["d_obj"]) if r["d_obj"] > 0 else (0.0, r["d_bal"])
            else:                                     # solvent: maximize X, stay solvent
                if new_bal < 0 or r["d_obj"] <= 1e-6:
                    continue
                score = (1.0, r["d_obj"])
            if best is None or score > best[0]:
                best = (score, r)
        if best is None:
            break
        r = best[1]; n = r["policy"]; s = settings.get(n, 0.0)
        settings[n] = min(1.0, max(0.0, s + (step if r["dir"] == "+" else -step)))
        history.append({"policy": n, "dir": r["dir"], "d_obj": r["d_obj"], "d_bal": r["d_bal"]})
    fo, fb, feq = ev(settings)
    return {"settings": settings, "obj": fo, "balance": fb, "history": history, "equilibrium": feq}


def gradient_optimize(model, p0, exo, objective, ab, csv_cost_k, csv_income_k, *,
                      init_values=None, init_active=None, freeze_active=True,
                      lr=0.15, max_step=0.15, steps=25, fd_eps=0.05, deficit_penalty=12.0,
                      surplus_penalty=0.0, bal_scale=100.0, tol=1e-3, lr_decay=0.06, policies=None):
    """Projected-gradient optimizer — EXPERIMENTAL / numerically finicky (balance $Bn-scale vs X unit-
    scale makes the penalty ill-conditioned; a higher lr or surplus penalty diverges). Superseded for the
    hard balance constraint by the planned SLP (linearize + LP-solver step). `greedy_optimize` is the
    trustworthy optimizer for now. Kept for reference / the inverse-problem framing.

    Ascends  L(p) = X(eq(p)) - deficit_penalty*|min(0,bal)|/scale - surplus_penalty*max(0,bal)/scale,
    i.e. drive the budget toward ~0 (strongly avoid deficit, mildly discourage hoarding a surplus so
    freed money is spent on the objective), then maximize X. Numerical gradient through the equilibrium;
    one step moves ALL policies (far fewer solves than greedy), projected to [0,1], lr decays for
    convergence. Deterministic given p0 — call from several starts to surface alternate optima.
    """
    plist = list(policies or model.policies)
    p = {n: float(p0.get(n, 0.0)) for n in model.policies}   # held; only plist moves (see slp_optimize)

    def L(settings):
        o, b, eq = evaluate(model, settings, exo, objective, ab, csv_cost_k, csv_income_k,
                            init_values, init_active, freeze_active)
        bal_term = (deficit_penalty * (b / bal_scale)) if b < 0 else (-surplus_penalty * (b / bal_scale))
        return o + bal_term, o, b

    trace = []
    for t in range(steps):
        lr_t = lr / (1.0 + lr_decay * t)
        baseL, baseO, baseB = L(p)
        grad = {}
        for n in plist:
            up = min(1.0, p[n] + fd_eps)
            sign, probe = (1.0, up)
            if abs(up - p[n]) < 1e-12:               # at upper bound → probe downward
                probe, sign = max(0.0, p[n] - fd_eps), -1.0
            pp = dict(p); pp[n] = probe
            l, _, _ = L(pp)
            grad[n] = sign * (l - baseL) / fd_eps
        gnorm = max(abs(g) for g in grad.values()) if grad else 0.0
        for n in plist:
            stepn = max(-max_step, min(max_step, lr_t * grad[n]))
            p[n] = min(1.0, max(0.0, p[n] + stepn))
        trace.append({"L": baseL, "obj": baseO, "balance": baseB, "gnorm": gnorm})
        if gnorm < tol:
            break

    fo, fb, feq = evaluate(model, p, exo, objective, ab, csv_cost_k, csv_income_k,
                           init_values, init_active, freeze_active)
    return {"settings": p, "obj": fo, "balance": fb, "trace": trace, "equilibrium": feq}


def slp_optimize(model, p0, exo, objective, ab, csv_cost_k, csv_income_k, *,
                 init_values=None, init_active=None, freeze_active=True,
                 delta=0.25, iters=40, fd_eps=0.05, tol=1e-3, policies=None,
                 balance_min=0.0, balance_max=None,
                 eta_accept=0.1, eta_expand=0.75, delta_min=0.002, delta_max=0.5,
                 mu_min=0.0):
    """Sequential Linear Programming with a real trust region -- the principled local optimizer.

    Each iteration linearizes X and the budget balance through the equilibrium by finite differences,
    then solves an LP for the best step inside a trust region. What makes it a *trust-region* method,
    and what the earlier version of this function lacked, is the last part of that loop:

    * an **exact ell-1 penalty merit function** ``phi = X - mu * violation(balance)`` gives one number
      that ranks any two points, so restoring the budget and improving X stop being separate phases
      that can undo each other;
    * ``mu`` is set from the measured gradient ratio ``max|dX/dp| / max|dBalance/dp|``, which is what
      makes the penalty scale-free -- the ill-conditioning that made the projected-gradient version
      diverge was $Bn and X-units being compared with a hand-tuned constant;
    * the LP is **elastic** (violation enters as a penalized slack), so a step always exists and no
      separate feasibility phase is needed; and
    * every step is **tested before it is kept**. The ratio ``rho`` of actual to predicted merit gain
      decides: reject and shrink the region when the linear model was lying, accept and expand it when
      the model was good. The previous version accepted every LP step unconditionally and shrank the
      region on a fixed decay schedule regardless, which is why its trace was non-monotone in X and
      swung the balance by over $1500Bn between iterations.

    ``balance_max`` is a genuine constraint when supplied (it replaces the old ``surplus_cap`` hack of
    capping the LP step): the merit function penalizes overshoot above it symmetrically.
    """
    import pulp

    plist = list(policies or model.policies)
    # `policies` restricts what may MOVE, not what exists. The rest of the vector is held at p0 --
    # dropping it would delete those policies from the state entirely, and any effect formula that
    # references one by name then fails to resolve.
    p = {n: float(p0.get(n, 0.0)) for n in model.policies}

    def ev(settings):
        return evaluate(model, settings, exo, objective, ab, csv_cost_k, csv_income_k,
                        init_values, init_active, freeze_active)

    def violation(b):
        v = max(0.0, balance_min - b)
        if balance_max is not None:
            v += max(0.0, b - balance_max)
        return v

    base_obj, base_bal, _ = ev(p)
    radius, mu = delta, 0.0
    trace = []

    for _ in range(iters):
        # Measure the gradient at the scale the step will actually be taken; a difference taken over
        # 0.05 says little about a move of 0.001, and the mismatch shows up as a meaningless rho.
        eps_t = max(min(fd_eps, radius), delta_min)
        gX, gB = {}, {}
        for n in plist:
            probe, sign = min(1.0, p[n] + eps_t), 1.0
            if abs(probe - p[n]) < 1e-12:                # at the upper bound -> probe downward
                probe, sign = max(0.0, p[n] - eps_t), -1.0
            pp = dict(p)
            pp[n] = probe
            o, b, _ = ev(pp)
            gX[n] = sign * (o - base_obj) / eps_t
            gB[n] = sign * (b - base_bal) / eps_t

        # Penalty weight. An exact ell-1 penalty needs mu above the constraint's Lagrange multiplier;
        # the LP hands us an estimate of exactly that as the shadow price on the balance row, so the
        # first pass seeds mu from the gradient ratio and every later pass raises it to clear the
        # measured dual. mu only ever increases -- that is what makes the penalty exact.
        mx = max((abs(v) for v in gX.values()), default=0.0)
        mb = max((abs(v) for v in gB.values()), default=0.0)
        if mb > 1e-12:
            mu = max(mu, mu_min, 4.0 * mx / mb)

        prob = pulp.LpProblem("slp_step", pulp.LpMaximize)
        d = {n: pulp.LpVariable(f"d{i}", lowBound=max(-radius, -p[n]),
                                upBound=min(radius, 1.0 - p[n]))
             for i, n in enumerate(plist)}
        s_lo = pulp.LpVariable("s_lo", lowBound=0.0)      # elastic slack: shortfall below balance_min
        s_hi = pulp.LpVariable("s_hi", lowBound=0.0)      # elastic slack: overshoot above balance_max
        bal_lin = base_bal + pulp.lpSum(gB[n] * d[n] for n in plist)
        prob += bal_lin >= balance_min - s_lo, "bal_floor"
        if balance_max is not None:
            prob += bal_lin <= balance_max + s_hi, "bal_cap"
        else:
            prob += s_hi == 0, "no_cap"
        prob += pulp.lpSum(gX[n] * d[n] for n in plist) - mu * (s_lo + s_hi)
        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        # Raise mu to clear the shadow price on the budget row and re-solve, so the step we test is
        # the one a correctly-weighted penalty would have chosen.
        try:
            pi = abs(float(prob.constraints["bal_floor"].pi or 0.0))
        except (KeyError, TypeError, ValueError):
            pi = 0.0
        if pi > mu:
            mu = 2.0 * pi
            prob.objective = pulp.lpSum(gX[n] * d[n] for n in plist) - mu * (s_lo + s_hi)
            prob.solve(pulp.PULP_CBC_CMD(msg=0))

        step = {n: (d[n].value() or 0.0) for n in plist}
        move = max((abs(v) for v in step.values()), default=0.0)

        # predicted vs actual improvement in the merit function
        pred = (float(pulp.value(prob.objective) or 0.0)
                + mu * violation(base_bal))              # model merit gain relative to d = 0
        cand = dict(p)
        for n in plist:
            cand[n] = min(1.0, max(0.0, p[n] + step[n]))
        new_obj, new_bal, _ = ev(cand)
        actual = (new_obj - mu * violation(new_bal)) - (base_obj - mu * violation(base_bal))
        rho = actual / pred if pred > 1e-12 else (1.0 if actual > 0 else -1.0)

        accepted = rho >= eta_accept
        if accepted:
            p, base_obj, base_bal = cand, new_obj, new_bal
        trace.append({"obj": base_obj, "balance": base_bal, "merit": base_obj - mu * violation(base_bal),
                      "radius": radius, "rho": rho, "move": move, "accepted": accepted, "mu": mu})

        if rho < 0.25:
            radius *= 0.5
        elif rho > eta_expand and move >= 0.9 * radius:
            radius = min(delta_max, radius * 2.0)

        if radius < delta_min or (accepted and move < tol and violation(base_bal) <= 1e-9):
            break

    fo, fb, feq = ev(p)
    return {"settings": p, "obj": fo, "balance": fb, "trace": trace, "equilibrium": feq,
            "feasible": violation(fb) <= 1e-9}


__all__ = ["make_objective", "evaluate", "marginal_analysis", "rank_moves",
           "greedy_optimize", "gradient_optimize", "slp_optimize"]
