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

**Layer 2 — the optimizer.** Proposes policy vectors; **every candidate is scored by Layer 1**.
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
- [x] **Layer 1 — equilibrium solver.** Running against the live game CSVs: converges in ~50
      iterations, situations resolved self-consistently via hysteresis, budget reconstructed from the
      save's anchors. **Not yet validated against an independent oracle** — see the open item below.
- [x] **Layer 2 — optimizer.** Both halves built; see [`notes/layer2.md`](notes/layer2.md).
      **Trust-region SLP** (`optimize.slp_optimize`) — local, situations frozen, ℓ1-penalty merit
      function with step acceptance and an adaptive region. **MILP** (`milp.refine_milp`) — the whole
      network as one mixed-integer program in ~514 binaries, with the **situation flags as decision
      variables**, so it can search for a basin escape rather than inheriting one. Every candidate from
      either is re-scored by Layer 1, which remains the arbiter.
- [ ] **Validate Layer 1 against an independent oracle.** The current check is against a turn-1
      savegame — a *transient*, not an equilibrium. `data/simulation/data_dump/{inputs,outputs}` is the
      oracle this repo's `CLAUDE.md` names, but both directories ship **empty**: the game only writes
      them under some debug condition we have not found. That prerequisite is the real blocker.
- [ ] **Un-zero the finance + membership subsystems.** `_effectivedebt_`, `_global_interest_rates_` and
      the `*_perc` membership values are still unresolved sources (11 are reported in
      `MilpSolution.problems` on every MILP run), so loop gain is too low to hold the game's doom basin.
      `data/simconfig.txt` (interest rates, credit ratings, `DEBT_TO_GDP_MAX`) and `data/missions/*/`
      (per-country income bands, GDP range, population, starting debt) are shipped, grounded, and not
      yet read by the loader.
- [ ] **Make the budget's economy sensitivity uniform.** `AnchoredBudget.cost` takes no state argument,
      so the 46 policies enacted in the save are economy-blind while the 77 CSV-estimated ones carry the
      GDP multipliers — 7 policies have a declared GDP multiplier silently discarded. Because of this the
      savings-buffer assumption in `notes/scope.md` is **not measurable**: sweeping the status-quo vector
      across the whole economic cycle gives a perfectly flat balance (`scripts/economy_sweep.py`).

## Setup

```bash
cp config.example.toml config.toml   # then point data.sim_dir at your Democracy 3 install
python -m pip install -e ".[dev]"
pytest
```

Or set `D3_SIM_DIR` instead of editing `config.toml`. The game CSVs are read in place (single source
of truth — no copy, no drift).

**You also need a savegame.** The scripts under `scripts/` read
`tests/fixtures/autosave_usa_turn1.xml` — the US start, turn 1 — for the policy vector, the situation
set, and the per-policy cost/income anchors. It is **not in the repo**: a savegame embeds Positech's
mission data and the whole game state, and this repo is public. Produce your own by starting a US game
and playing one turn, then copy the autosave to that path. `tests/fixtures/*.xml` is gitignored. The
test suite needs none of this — all 38 tests are synthetic and run on a bare clone.

## Layout

```
src/d3solver/
  formula.py   effect-formula parser + safe evaluator
  model.py     typed model (SimValue, Policy, VoterType, Situation, Effect, GameModel)
  loader.py    CSV loaders; collects parse problems, never fabricates
  config.py    resolve the data dir (env or config.toml)
  scenario.py  exogenous inputs; economy defaults to its long-run average, and sweeps
  network.py   reverse adjacency: target -> incoming edges
  savegame.py  autosave.xml parser (policy settings, sim values, situation flags)
  solver.py    Layer 1 — the iterative equilibrium fixed point (the oracle)
  budget.py    reconstructed cost/income, anchored to the save's $ figures
  optimize.py  Layer 2 local — marginal frontier, greedy, and the trust-region SLP
  pwl.py       Layer 2 support — affine detection + error-driven piecewise-linear grids
  milp.py      Layer 2 global — the network as a MILP, with situation flags as binaries
notes/grammar.md   the CSV grammar, grounded in the shipped data
notes/scope.md     the agreed problem statement
notes/layer2.md    the two optimizers: encoding, what is approximate, how to read the results
notes/findings.md  what the model actually says - reproducible comparisons off the bench
web/               browser bench: template + optimiser-derived scenarios
scripts/           runnable drivers (solve_us, frontier, optimize_*, milp_us, economy_sweep,
                   export_scenarios, export_web_model, build_explorer,
                   cost_effectiveness - outcome per $Bn, ranked, per target)
tests/             formula, PWL, and MILP-vs-solver agreement tests
```
