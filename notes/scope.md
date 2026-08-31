# Scope & problem statement

> Agreed with Chris 2026-08-10. This is the spec the simulator and optimizer are built to. When code
> and this doc disagree, we reconcile deliberately — don't let either drift silently.

## What this is (and isn't)

A **strategic optimizer**, not a gameplay simulator. The question it answers:

> *Given an objective function **X** over the country's state, what policy settings maximize X,
> subject to a stable (non-deficit) budget?*

There is **no single "solution."** Different X → different optimal state, and all are valid: an
anarcho-capitalist optimum (near-zero tax, lower longevity) and a full-welfare optimum (90% tax, best
amenities) are both correct answers to different X. The deliverable is the **machine that maps any X to
its optimal policy configuration** — effectively a Pareto-frontier explorer over the game's own model.

## The formal problem

```
maximize    X( s* )
over        policy settings  p ∈ [0,1]^n        (0 = not enacted; continuous slider)
where       s* = equilibrium state of the effect network given p   (a fixed point)
subject to  budget_balance(s*) ≥ 0              (no deficit — deficits are unstable)
            node clamps:  min_i ≤ s*_i ≤ max_i
```

**"Best return per $" is the shadow-price structure of this problem, not a separate objective.** The
budget constraint's multiplier λ is the marginal value of a dollar in X-units; each policy is funded
until its marginal ∂X/∂$ falls to λ (return > λ → max, < λ → zero, else interior). **Minimizing spend
is explicitly NOT the goal** — allocating each dollar to its highest marginal X is.

## In scope

- **Decision variables:** each policy's slider setting, continuous `p ∈ [0,1]`.
- **Transfer function:** the full effect network solved to **equilibrium**. Outcomes (GDP, Health,
  CrimeRate, Equality, Environment, CO2, Unemployment, …) **and** finances (tax income, spending,
  budget balance) are all first-class **endogenous** variables in one network.
- **Objective X:** user-defined, over outcomes + finances. Re-solved per X (LP re-derived each time).
- **Constraint:** `budget_balance ≥ 0`. Surpluses allowed (pay down debt / build savings); the
  optimizer won't create surplus unless X rewards it.

## Out of scope (dropped)

Election/vote computation, cynicism-as-vote-driver, assassination/plots, political capital (action
points), implementation delay (inertia), country choice beyond initial conditions, electability. Voter
groups survive only as **silent internal variables** (a few feed back into outcomes like GDP); their
approval is never an objective target unless explicitly chosen.

## Finance model (reconstructed from the CSVs — all endogenous)

- **Tax income** = income_range × rate-factor × multipliers(GDP, `TaxEvasion`, group size). Higher
  rates raise `TaxEvasion` → **diminishing revenue** (built into the data).
- **Policy cost** = cost_range × multipliers (often × GDP / demand). Governing a rich country costs more.
- **Balance** = Σincome − Σcost − interest(debt). Treasury & national **debt are engine-accumulated,
  not CSV nodes**; consequences surface as the `DebtCrisis` situation + credit-rating events. Phase 1
  (option A) uses **annual balance** as the financial equilibrium variable; debt level is a fixed
  scenario input, not a tracked stock. The debt→credit-downgrade→higher-interest→more-debt loop is why
  `balance ≥ 0` is imposed as a rule rather than re-derived each run.

## Open mechanics (homework — empirical, not scope decisions)

1. ~~**Combination rule**~~ — **RESOLVED 2026-08-10**: `value = clamp(default + Σ influenceᵢ)`,
   confirmed against the US save (`scripts/check_combination.py`). See `notes/grammar.md`.
2. **Situations** — load `situations.csv` into the edge index; active-state comes from the save
   (12 active in the US start). Needed for high-connectivity nodes (CrimeRate, Health, …).
3. **Exogenous globals** `_globaleconomy_`, `_year` — read from the save.
   - `_globaleconomy_` — **RESOLVED 2026-08-31.** The averaging decision below was *not* implemented:
     every script read `save.globals.get("globaleconomy_pos", 0.5)`, and since that key is always
     present the `0.5` fallback never fired, so all results ran at the save's momentary cycle position
     (0.3113 for the US start). `scenario.py` now owns this with the average as the default and the
     position as a sweepable parameter (`scripts/economy_sweep.py`).
   - `_year` — **OPEN, do not guess.** It is fed `globaleconomy_years = 8.0`, which is exactly
     `GLOBAL_ECONOMY_CYCLE_LENGTH_YEARS` in `data/simconfig.txt` — the cycle *length*, not elapsed
     time. Every other node is normalised to [0,1], so 8.0 is an order of magnitude out of range; it
     drives `_Terrorism +0.08` and `OilSupply −0.12`. What the engine actually passes for `_year` is
     unresolved. Left as-found deliberately rather than replaced with a plausible number.
6. **The budget has two incompatible halves** (found 2026-08-31 via `economy_sweep.py`).
   `AnchoredBudget.cost(name, setting)` takes **no state argument**: the 46 policies enacted in the save
   scale with the slider alone and are economy-blind, while the 77 CSV-estimated ones carry the GDP
   multipliers. Seven policies whose CSVs declare a GDP multiplier are anchored and have it discarded.
   Consequence: sweeping the status-quo vector across the whole economy cycle gives a **perfectly flat**
   balance, so the savings-buffer premise in the addendum below is currently **not measurable**.
   `data/missions/<country>/` (min/max GDP, income bands, `wealth_mod`, population, starting debt) is
   the grounded source that would make cost and income uniform — and would generalise past the US.
4. **Interest / credit-rating mechanic** — for debt-level scenarios and Phase B.
5. **Value normalization / ranges** per node (esp. voter opinions vs. [0,1] sim values).

## Addendum 2026-08-10 — equilibrium semantics & bistability

- **No steady state in the live game** (implementation delays, dilemmas, floating world economy,
  elections). We compute a **counterfactual equilibrium**: policies fully implemented + economy at its
  long-run **average** (`_globaleconomy_` is a parameter, default = average; sweepable for good/bad
  times). `balance ≥ 0` is enforced on the *average-economy* equilibrium; the cycle is buffered by
  **savings** (bank surplus in booms, draw down in busts). *Implementation:* `scenario.py`
  (`AVERAGE_ECONOMY = 0.5`, sweepable via `Scenario.with_economy`). *Status of the buffer claim:*
  untested — see open mechanic 6; the budget cannot currently express it.
- **The network is bistable.** Same policies admit a self-sustaining "doom-loop" basin (high crime ↔
  low GDP ↔ high unemployment, crime/health situations active) and a "virtuous" basin. The solver
  supports both: cold-start (from defaults) → virtuous; `--warm` (from a save's values+active set) →
  current basin.
- **Decision (Chris): optimize BOTH basins and compare** — report the optimum in each and flag when a
  doom loop is sticky (can't be escaped by the found policy). The interesting question is "can these
  policies pull the country from its current basin into a better one?"
- **Reproducing the game's basin needs the finance + membership subsystems** we currently zero
  (`_effectivedebt_`, `_global_interest_rates_`, `*_perc`); without them our loop gain is too low to
  hold the doom basin. So finance is the next build — also core to `balance ≥ 0`.

## Phases

- **Phase 1:** equilibrium simulator (the oracle) + the constrained optimization above, for a chosen X,
  `balance ≥ 0`. Validate the simulator against the running game.
- **Phase 2 (later):** debt trajectory over a horizon (option B); then feasibility — political capital,
  implementation delay — i.e. *how to actually get there*.
