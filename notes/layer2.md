# Layer 2 — the two optimizers, and what each one's number means

> Built 2026-08-31. Layer 2 is the optimizer that sits on the equilibrium simulator. There are two of
> them because they answer different questions, and reading their outputs as interchangeable is the
> main way to get the wrong answer out of this repo.

Both maximize a user-defined `X` over the equilibrium state subject to `balance ≥ 0`, and **both are
scored by Layer 1** — the exact nonlinear fixed-point solver — never by their own internal model.

| | `optimize.slp_optimize` | `milp.refine_milp` |
|---|---|---|
| Method | Sequential Linear Programming in a trust region | whole network as one MILP, plus a budget-refinement loop |
| Scope | **local** — walks from a starting vector | **global-ish** — searches the whole box at once |
| Situations | **frozen** (`freeze_active=True`) | **decision variables** — it picks the basin |
| Cost | ~15 iters × 123 equilibrium solves | ~6 CBC solves of ~514 binaries |
| Driver | `scripts/optimize_slp_us.py` | `scripts/milp_us.py` |

## The MILP encoding

Three measurements from the shipped data decide the whole design, and they were taken before any
solver was written:

* **1022 of 1149 edges (89%) are affine** in their source value. They enter the MILP exactly, at zero
  cost in binaries and zero approximation error.
* The nonlinear remainder (96 powers, `x^0.4` through `x^11`, plus 18 constants) reads only **57
  distinct source nodes**. A piecewise-linear grid belongs to a *source*, not an edge, because every
  formula reading that source is a function of the same scalar — so all of them share one set of
  `delta`/`z` variables. That is what keeps the model at ~514 binaries instead of thousands.
* Breakpoints are placed by **error-driven refinement**, not uniformly. `x^11` is flat across most of
  `[0,1]` and then turns almost vertically; a uniform grid spends its resolution where the curve is
  already a line and loses it exactly where it is not.

The clamp `v = clamp(z, min, max)` gets binaries **only on the side that can actually bind**, decided
by interval arithmetic over each node's incoming range — most nodes need none.

### Situations are the interesting part

A situation is a node with a start trigger and a *lower* stop trigger. At equilibrium the
self-consistency condition is:

```
active   =>  value >= stop_trigger
inactive =>  value <= start_trigger
```

Between the two triggers **both assignments satisfy both constraints**. That band is not a modelling
wart — it *is* the bistability `notes/scope.md` describes, written as a constraint, and a binary is
exactly the right variable for it. Giving the solver that binary is what lets it search for a basin
escape, which is the question the SLP cannot even ask: freezing the situation set *is* pinning the
basin.

## What is approximate (all of it can make the MILP optimistic)

1. Piecewise-linear segments approximate the power curves — worst observed error **3.05e-02**
   (`AbortionLaw: 0.2-(x^5)`), reported as `MilpSolution.max_pwl_error`.
2. The 13 edges of the form `g(x) * OtherNode` are relaxed with **McCormick envelopes**. The product
   form is *verified numerically* per formula before being relied on, not assumed from the grammar.
3. Policy cost/income are linear through the origin with their multiplier factors held at a reference
   state. Through the origin deliberately: an affine fit with a positive intercept would hand the
   solver free income at `s = 0`, and it would take it.

Hence `MilpSolution.milp_objective` is a **proposal and a bound, never a result**.

## Why the MILP needs an outer loop

The first solve of the US start returns a vector its own linear budget scores at **$0Bn** and the
exact solver scores at **−$899Bn**. The linear budget is not wrong — it is exact at the reference
state, verified per-policy — but policy costs are multiplied by *endogenous* factors, dominantly GDP.
Move GDP, which is precisely what a good policy set does, and every cost in the country moves with it.

`refine_milp` therefore gives the budget the same treatment as everything else here: propose against
a linearisation, verify against the oracle, **re-linearise where the oracle actually landed**, repeat.
A `margin` term absorbs the shortfall the oracle reports and relaxes once it stops binding. Converged
on the US start in 4 rounds.

## Scenario: which economy are we optimizing at?

`notes/scope.md` fixes the world economy at its **long-run average** and lets savings absorb the cycle.
The scripts did not do that. Every one built its exogenous dict with
`save.globals.get("globaleconomy_pos", 0.5)` — and that key is present in every save, so the `0.5`
fallback never fired and every result this project had produced was computed at the save's momentary
cycle position (**0.3113** for the US start: a below-average economy).

`scenario.py` now owns that construction, with the economy as an explicit parameter defaulting to the
average, which also makes scope.md's "sweepable for good/bad times" a real capability rather than a
sentence. **All numbers below are at economy = 0.5.**

`_year` is deliberately left as found — it is fed `globaleconomy_years = 8.0`, which is exactly
`GLOBAL_ECONOMY_CYCLE_LENGTH_YEARS` from `data/simconfig.txt`, i.e. the cycle *length*, not elapsed
time. Every other node here is normalised to [0,1]. It is flagged, not guessed at; see `notes/scope.md`.

## Results on the US start (welfare basket + GDP, `balance ≥ 0`, economy = 0.5)

Status quo: `X = +0.238`, balance `−$97Bn`, 12 situations active.

| Optimizer | X (Layer-1 verified) | balance | basin |
|---|---|---|---|
| greedy (pre-existing) | +1.44 | ~$0Bn | frozen |
| **trust-region SLP** | **+3.000** | +$4Bn | **frozen** |
| **MILP + refinement** | **+2.905** | +$140Bn | **free — escaped 7 of 12, entered 8** |

### Read these two numbers carefully

`X = 3.000` is the **theoretical ceiling** of this weight basket, not a solver artifact: all six
objective nodes sit exactly on their CSV clamp bounds (`Equality = Health = GDP = 1`,
`PovertyRate = Unemployment = CrimeRate = 0`). It is also **conditional on the frozen basin**. Re-score
that same policy vector with the situations released and it falls to **X = 2.788 at −$42Bn — infeasible**.

So the SLP's higher number is the less trustworthy one. The MILP's `+2.905` is lower *and*
self-consistent under the exact solver with situations free. When the two disagree, the one that did
not assume its basin wins.

**This objective saturates**, which makes it a weak test of the machinery: once every component can be
maxed at once there is no tradeoff left, and the "no single solution / Pareto frontier" premise in
`notes/scope.md` is never exercised. A basket that actually competes (GDP against Equality at a fixed
budget) would be the sharper next probe.

## Does the savings buffer cover the busts? (`scripts/economy_sweep.py`)

Scope.md enforces `balance ≥ 0` at the average on the reasoning that booms bank a surplus that pays
for busts. That is testable: hold a policy vector fixed and re-solve across the economy's range.

Sweeping the SLP optimum, balance runs **min −$21Bn, mean −$3Bn, max +$4Bn** — summed surplus $25Bn
against summed deficit $53Bn. The mechanism behind the asymmetry is worth naming: the optimizer drives
**GDP to its clamp of 1.0**, so above economy ≈ 0.5 the upside stops growing while the downside keeps
costing. *A buffer cannot be filled by booms that are capped.*

**But the sweep cannot yet settle the question, and the reason is a defect in the budget model.**
Sweeping the *status-quo* vector gives a balance that is **perfectly flat at −$97Bn across the entire
cycle** — because `AnchoredBudget.cost(name, setting)` takes no state argument at all. The 46 policies
enacted in the save scale with the slider alone and are **economy-blind by construction**; only the 77
CSV-estimated ones carry the GDP multipliers. Seven policies whose CSVs explicitly declare a GDP
multiplier are anchored, and have that term silently discarded.

So the budget has two incompatible halves, and only one of them can feel the economy. Until that is
uniform, the savings-buffer premise is **not measurable** — which is a concrete, grounded reason to
read `data/missions/<country>/` (`min_gdp`/`max_gdp`, `min_income`/`max_income`, `wealth_mod`,
`population`, `starting_debt`): those are the constants that would let cost and income be computed
from the state for *every* policy, instead of anchored-to-a-screenshot for a third of them.

## Open

- The saturating objective above — pick a basket with a real internal tradeoff.
- MILP `bound` is reported but CBC returns the trivial bound here (X = 3.000 is attainable), so it
  certifies nothing yet on this basket.
- Both optimizers inherit Layer 1's open validation gate: the equilibrium itself is still checked only
  against a turn-1 *transient*, and the six zeroed subsystems (`_effectivedebt_`,
  `_global_interest_rates_`, `*_perc`) are unresolved sources here too — 11 of them are reported in
  `MilpSolution.problems` on every run.
