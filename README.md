# democracy3-solver

> Can you *solve* Democracy 3 with game data + optimization? This project extracts Positech's
> Democracy 3 simulation model straight from its shipped CSVs, rebuilds the equilibrium as a faithful
> simulator, then runs an optimizer on top that answers: **given an objective function X over the
> country's state, what policy settings maximize X under a non-deficit budget?** See
> [`notes/scope.md`](notes/scope.md) for the agreed problem statement — it's a strategic optimizer, not
> a gameplay/election simulator.

## Why this is tractable

Democracy 3's entire model is **data, not code**: `data/simulation/*.csv` defines a feedback network
of ~40 simulation values, ~123 policies, 21 voter groups, and situations. Every node emits **effects**
— polynomial functions of a source value `x`, optionally lagged by *inertia*. A turn resolves the
network toward a fixed point; vote share is read off the voter groups. See
[`notes/grammar.md`](notes/grammar.md) for the full grammar.

## Architecture — two layers

**Layer 1 — the grounded equilibrium simulator (the oracle).** Parse the CSV grammar and faithfully
execute it: given a policy vector, compute the equilibrium state, budget, and vote share. This is a
*conversion* of the game's own data (cross-checkable against the running game), not a rebuild — so it
doubles as the verifier for everything above it.

**Layer 2 — the optimizer (later).** Proposes policy vectors; **every candidate is scored by Layer 1**.
- **Linearized LP** around an operating point → marginal analysis ("best votes-per-$ move now").
- **MILP** (piecewise-linear the polynomial effects + binary situation triggers) → global-ish solve.
- Objective is **user-defined X over outcomes + finances**, maximized s.t. `budget_balance ≥ 0`. There
  is no single solution — different X give different optimal states (see `notes/scope.md`). "Best return
  per $" is the budget constraint's shadow price, not a separate goal; minimizing spend is *not* the aim.

Why LP is an approximation, not the native form: effects are polynomials in `x` (`x^4`, `x^6`, …) and
the system is a coupled fixed point (GDP → everything → GDP), so it's a nonlinear program. LP/MILP are
the tractable approximations; the simulator keeps them honest.

## Status

- [x] **Layer 0 — data ingestion.** CSV + effect-formula parser; loads the real game data, evaluates
      formulas, and *surfaces* the 6 malformed effects shipped in the CSVs instead of guessing.
- [x] **Scope agreed** — see [`notes/scope.md`](notes/scope.md): strategic optimizer, finances
      first-class/endogenous, `balance ≥ 0`, voting/capital/delay out of scope.
- [x] **Combination rule — confirmed** (`scripts/check_combination.py` vs the US save):
      `value = clamp(default + Σ influenceᵢ)`. See `notes/grammar.md`.
- [ ] **Layer 1 — equilibrium solver.** In progress: `savegame.py` (oracle parser) + `network.py`
      (incoming-edge index) done. Next: load `situations.csv` + active state from the save; add
      `_globaleconomy_`/`_year`; then the iterative fixed-point solve + endogenous budget.
- [ ] **Layer 2 — optimizer.** Constrained max of X s.t. `balance ≥ 0`: linearized LP → MILP.

## Setup

```bash
cp config.example.toml config.toml   # then point data.sim_dir at your Democracy 3 install
python -m pip install -e ".[dev]"
pytest
```

Or set `D3_SIM_DIR` instead of editing `config.toml`. The game CSVs are read in place (single source
of truth — no copy, no drift).

## Layout

```
src/d3solver/
  formula.py   effect-formula parser + safe evaluator
  model.py     typed model (SimValue, Policy, VoterType, Effect, GameModel)
  loader.py    CSV loaders; collects parse problems, never fabricates
  config.py    resolve the data dir (env or config.toml)
notes/grammar.md   the CSV grammar, grounded in the shipped data
tests/             formula tests (incl. the shipped typos)
```
