# Findings from the bench

> What the model actually says, as opposed to what we assumed it would say. Each entry is a
> comparison somebody can reproduce: `scripts/` or the browser bench, US start, economy at 0.5, with
> the situation set free to move unless noted. Kept because the whole point of the bench is to *train*
> our intuition before committing to an objective function — and so far it has mostly corrected it.

## Zero crime does not cost mass unemployment — it costs productivity

The motivating example for deferring the objective function was "is zero crime worth mass
unemployment?" The model's answer is that the question is built on a tradeoff that isn't there.

Optimising `-CrimeRate` alone (`scenarios.json` → `safety`), against the US start:

| | US start | zero-crime optimum | change |
|---|---|---|---|
| CrimeRate | 0.007 | **0.000** | −0.007 |
| Unemployment | 0.415 | **0.101** | **−0.314** |
| Equality | 0.239 | **0.827** | **+0.588** |
| GDP | 0.583 | 0.494 | −0.089 |
| Productivity | 0.727 | 0.384 | **−0.343** |

**Crime and unemployment move together here**, so driving one down drags the other with it. The real
price of zero crime is productivity and output, not joblessness. Any weight vector written from the
armchair would have mispriced this.

## Military spending and state pensions are not what their names say

Chris's question: the US's two largest spending lines are the debt drivers — what happens if you just
delete them? A grep of the raw data suggested only one dilemma plus voter backlash. The bench says
the transmission runs somewhere else entirely.

The two lines are **$463Bn of $1,288Bn — 36% of all spending** (Military $248Bn at level 0.88,
Pensions $215Bn at 0.51, on the save's own anchored cost figures).

| | balance | GDP | Unemployment | CrimeRate | PovertyRate | Equality |
|---|---|---|---|---|---|---|
| US start | −$97Bn | 0.621 | 0.384 | 0.008 | 0.254 | 0.218 |
| Military = 0 | +$151Bn | 0.515 | **0.651** | 0.112 | 0.260 | 0.262 |
| Pensions = 0 | +$118Bn | 0.613 | 0.387 | 0.117 | **0.356** | 0.138 |
| **Both = 0** | **+$366Bn** | 0.511 | **0.653** | **0.166** | 0.362 | 0.178 |

- **Military spending is a jobs programme.** Zeroing it takes unemployment 0.384 → **0.651**, a 70%
  jump that pulls GDP down with it, and raises Terrorism 0.20 → 0.33. New crises: **Cyber Warfare**
  and **Homelessness**. Genuine upside: CO2 0.94 → 0.81, Environment 0.30 → 0.42, and
  Environmentalists swing −0.13 → +0.18.
- **State pensions are an anti-poverty programme.** Zeroing them takes poverty 0.254 → 0.356,
  equality 0.218 → 0.138, and **crime up 12×**. Private Pensions rises 0.40 → 0.81 — the market
  partly fills the gap, but not for the people the policy was for. New crisis: **Homelessness**.
- **Together: crime rises 21×** (0.008 → 0.166) and terrorism nearly doubles.

The dilemmas barely register because dilemma pressure is weakly coupled to any single policy (see
below). The chain that actually bites is **spending → unemployment and poverty → crime → crisis
thresholds** — and crises are the sticky part, because hysteresis makes them far cheaper to cause
than to clear.

**This is the "number go up" failure in one screenshot.** An optimiser told to maximise the budget
balance returns exactly this: a **+$366Bn surplus with 65% unemployment and 21× crime**. It would be
arithmetically correct and completely useless, which is the argument for building the bench before
the objective.

## Dilemma pressure is weakly coupled to individual policies

Across a full 0→1 sweep of `MilitarySpending`, the largest movement of any state-driven dilemma's
pressure was **0.07**. The dilemmas that do respond are driven by `GDP`, `Health`, `Technology`,
`_LowIncome` and `PovertyRate` — broad economic aggregates — so they move on wholesale shifts in the
country's condition, not on a single lever. Worth knowing before hunting for a policy that "sets off"
a dilemma: mostly, none does.

(Also: 26 of the 54 dilemmas have no state-driven influence at all — they are a pure random roll, and
the bench excludes them rather than implying they can be predicted.)

## Crisis thresholds are findable, and that is the useful output

`MilitarySpending` swept from 0 to 1 on the US start, everything else held:

```
level   harmful crises   GDP     Unemp   Crime
0.65          8          0.582   0.467   0.072
0.70          7          0.585   0.454   0.013   <- threshold
0.88 (start)  7          0.583   0.415   0.007
```

**Military spending can be cut from 0.88 to 0.70 — about a fifth — with no crisis change at all.
Below 0.70, Homelessness starts and crime jumps roughly 6×.** That is the shape of answer the bench
exists to produce: not a score, but the level at which something breaks.

## Method note

Everything above was computed at the **average** world economy (0.5), not the save's own 0.3113 — see
`notes/scope.md` open mechanic 3. The budget figures come from the anchored half of the budget model,
which is grounded in the save's real dollar figures but is economy-blind; the caveat in
`notes/layer2.md` applies to any balance number that has to hold across the economic cycle.

## The real question: are they good *value*? (`scripts/cost_effectiveness.py`)

Establishing that military spending buys jobs and pensions buy poverty reduction settles nothing on
its own — everything in this model buys something, and the budget is finite. Paying people to march
around is *a* way to reduce unemployment; compelling saving is *a* way to reduce poverty. The question
is whether the same outcomes are cheaper somewhere else.

Ranking every enacted programme by **outcome per dollar** — remove it entirely, divide the target lost
by the money freed — says no, they are not good value.

**Buying jobs** (target: less unemployment, per $100Bn freed):

| programme | level | costs | unemployment it buys | per $100Bn |
|---|---|---|---|---|
| Border Controls | 0.40 | $3Bn | 0.1143 | **3.74** |
| Citizenship Tests | 0.22 | ~$0Bn | 0.0035 | 1.33 |
| Foreign Aid | 0.22 | $18Bn | 0.0816 | **0.45** |
| Intelligence Services | 0.78 | $39Bn | 0.1053 | 0.27 |
| Police Force | 0.55 | $36Bn | 0.0684 | 0.19 |
| Rail Subsidies | 0.45 | $64Bn | 0.0723 | 0.11 |
| **Military Spending** | 0.88 | **$248Bn** | 0.2673 | **0.11** |

Military spending is the **tenth** most cost-effective jobs programme the US is already running.
Border Controls delivers **43% of the military's entire employment effect for 1.2% of the money**.
Foreign aid is 4× better per dollar; intelligence services 2.5×.

**Buying poverty reduction** (target: less poverty, per $100Bn freed):

| programme | level | costs | poverty it buys | per $100Bn |
|---|---|---|---|---|
| Food Stamps | 0.82 | $21Bn | 0.0983 | **0.46** |
| Unemployed Benefit | 0.12 | $16Bn | 0.0143 | 0.09 |
| **State Pensions** | 0.51 | **$215Bn** | 0.1019 | **0.05** |
| State Schools | 0.35 | $102Bn | 0.0347 | 0.03 |

This one is stark. **Food stamps deliver essentially the same poverty reduction as state pensions —
0.0983 against 0.1019 — for one tenth of the money.** Pensions are a 10× worse buy for the outcome
they are nominally there to produce.

### There are outcomes you can buy for free

Twenty policies reduce unemployment *and* improve the balance. The largest: Import Tariffs (+0.0116),
Internet Tax (+0.0104), Gambling (+0.0067), and **Petrol Tax, which cuts unemployment and raises
$124Bn**. Ten do the same for poverty. Any budget that has not exhausted its free wins has no business
arguing about which expensive programme to fund — that is the shadow-price logic in `notes/scope.md`
made concrete: λ is not binding until the free moves are gone.

### What is grounded and what is not

**Every programme in the two tables above is enacted in the save**, so its cost is the game's own
dollar figure via `AnchoredBudget`, not an estimate. The head-to-head comparisons — military against
border controls, pensions against food stamps — are apples to apples.

The *marginal* "best buys" list is a mix. Rent Controls ($1Bn for the single best poverty ratio),
Winter Fuel Subsidy, Free School Meals, Healthcare Vouchers, Health Tax Credits and Rural Development
Grants are **not** enacted in the save, so their costs are CSV estimates scaled by a global
calibration factor. Treat a not-yet-enacted policy's price tag as an estimate, and a running
programme's as grounded.

Two further limits worth stating. These rankings are **single-target by construction** — that is what
makes them legible, and it also means they say nothing about what a cut does to everything else (see
the crises above). And *average* value assumes removing the whole programme, while *marginal* value
measures a nudge from where it sits; they diverge wherever returns diminish, which is most places.

### Replacement test: can you buy the same outcome cheaper?

Ranking says pensions are poor value. The replacement test proves it constructively — zero the
programme, then greedily buy the lost outcome back with whatever gives the most per dollar
(`--replace StatePensions --target poverty`):

```
cut State Pensions          frees $215Bn, costs 0.1019 of poverty reduction
buy back, best value first:
  Rent Controls        0 -> 1.00     +0.0300 total, ~$1Bn
  Food Stamps       0.82 -> 1.00     +0.0216      , ~$5Bn
  Winter Fuel Subsidy  0 -> 0.15     +0.0090      , ~$6Bn
  Free School Meals    0 -> 0.45     +0.0495      , ~$14Bn

RESULT   poverty  0.2540 -> 0.2430   (111% recovered — better than the original)
         balance  -$97Bn -> +$196Bn  ($293Bn better)
```

**State pensions are not the efficient way to buy less poverty: the same outcome — slightly better,
in fact — is available for $293Bn less.** The whole replacement portfolio costs roughly $26Bn against
the $215Bn it displaces.

**How much of this survives the budget model's weak half?** The $215Bn freed is grounded (pensions are
enacted in the save). Of the ~$26Bn replacement cost only Food Stamps is grounded; Rent Controls,
Winter Fuel Subsidy and Free School Meals are CSV-estimated. So the *saving* is the difference between
a solid number and a soft one — but the soft one would have to be underestimated by **more than 8×**
before the conclusion reverses. The direction is robust even if the magnitude is not exact.

### The same test on military spending — and why its headline number is overstated

`--replace MilitarySpending --target jobs`:

```
cut Military Spending      frees $248Bn, costs 0.2673 of unemployment reduction
RESULT   unemployment  0.3837 -> 0.3820   (101% recovered)
         balance       -$97Bn -> +$797Bn  ($894Bn better)
```

The employment effect *is* fully replaceable, and **the entire replacement portfolio cost nothing** —
every move the greedy took was revenue-neutral or revenue-raising (Import Tariffs, Gambling,
Citizenship Tests, School Prayers, plus Sales Tax and Income Tax rises).

**But $894Bn overstates the result, and the reason is a property of the search, not of the world.**
Free moves always outrank paid ones, so once the greedy runs out of *good* free moves it keeps taking
*trivial* ones — Income Tax to 0.49 raised **$288Bn for +0.0003** of unemployment. That is a revenue
decision wearing a jobs move's clothes. Roughly $646Bn of the $894Bn is revenue the jobs target never
required.

The defensible claim is the narrower one: **the military's entire employment effect can be replaced
without spending a dollar.** Not: the replacement earned $894Bn.

Grounding is also weaker here than in the pensions case. The biggest single contributor is Import
Tariffs (+0.0384 across three steps), which is **not enacted in the save** — a CSV estimate. Sales
Tax, Income Tax and Citizenship Tests are grounded; Import Tariffs, Gambling, Internet Tax and School
Prayers are not. So military spending being poor value for jobs is solid (that ranking is entirely
grounded), but *this particular replacement portfolio* leans on estimated policies more than the
pensions one did.

**Method note on the greedy.** An earlier run recovered only 41% because every free win scored as
infinite value, so ties broke arbitrarily and the move budget went on `+0.0000` gains. Free moves now
rank by size among themselves, which took the same test from 41% to 101%. A ratio that divides by zero
cannot order the things it returns infinity for — they need their own key.

## Can the budget be grounded in the CSVs instead of a savegame? Yes — a bug was hiding it

Chris asked whether the cost model could be grounded in the CSVs rather than anchored to a save.
`budget.py` said no, on the grounds that the CSV's cost and income figures are in different internal
units. Checking that claim instead of accepting it turned up something else: **`raw_cost` was
returning *negative or zero* costs for four of the five largest US programmes.**

| policy | raw_cost (before) | actual |
|---|---|---|
| Military Spending | **−425.6** | $248Bn |
| State Pensions | **0.0** | $215Bn |
| State Schools | −201.8 | $102Bn |
| Police Force | −67.5 | $36Bn |

The cause is one line of grammar. `notes/grammar.md` states that **`_default_,k` sets a constant base
term**, and `_multiplier_value` was multiplying by it like any other factor. For
`_default_,1.0;Wages,-0.1+(0.2*x)` at Wages = 0.26 the correct value is `1.0 + (−0.048) = 0.952`;
multiplying gives `−0.048`. The sign inverts, and the biggest programmes in the game price at less
than nothing.

Fixed: a `_default_` term is a base the other factors *add* to; without one the factors multiply as
before. With that corrected, **31 of the 32 enacted policies agree on a single CSV→$ conversion
constant to within ±11%** (median **0.0265** in the save's calibrated frame):

```
State Pensions 0.0257   Border Controls 0.0259   Foreign Aid 0.0259
Pollution Ctrl 0.0260   Space Program   0.0260   ... 31 of 32 inside 0.024–0.030
```

One conversion constant across 31 independent policies is not a coincidence — it is the unit scale.
So CSV grounding is reachable, and needs exactly two more things:

1. **The `*_perc` membership values.** The single outlier is Food Stamps (0.0078), whose multiplier
   reads `Poor_perc` — one of the values the network references but never defines, so `state.get`
   substitutes the *policy setting*. Same story for Winter Fuel Subsidy's `Retired_perc`.
2. **The unit constant derived rather than calibrated.** 0.0265 currently comes out of the save's
   $1,191Bn/$1,288Bn anchors. `data/missions/<country>/` ships `population`, `min_gdp`/`max_gdp`,
   `min_income`/`max_income` and `wealth_mod` — the obvious candidates for computing it from first
   principles, which would drop the savegame dependency completely and generalise to all six
   countries at once.

### Correction to the marginal rankings above

The bug did not touch the average-value tables — every programme in them is anchored, so `raw_cost`
was never called. It did not touch either replacement portfolio — none of those policies use
`_default_`. Only **7 of 123** policies use it at all, and five are anchored.

But two are not, and both were reported above as the top jobs buys:

| | reported | actual |
|---|---|---|
| Healthcare Vouchers | $0Bn, **19.87** per $100Bn | $115.7Bn, **0.0053** |
| Health Tax Credits | $0Bn, **18.83** per $100Bn | $60.0Bn, **0.0050** |

They were not the best buys in the game; they are among the worst, and they looked free because their
cost multiplier had been sign-inverted. **A policy that appears to deliver an outcome for nothing is a
bug report, not a bargain** — the same instinct that flagged `X = 3.000` as worth checking should have
flagged a $0Bn price tag on a $115Bn programme.

## Ancapistan: what the model says about a state with no revenue

Run for fun, but it produced a real result and a real bug. With `balance >= 0` and zero taxation,
income is zero, so spending must be zero too. That leaves **12 of 123 policies** — the ones that cost
nothing and raise nothing, i.e. pure law: Abortion Law, Alcohol Law, Ban Sunday Shopping, Creationism,
Death Penalty, Gambling, Gated Communities, Legalize Prostitution, Maternity Leave, Narcotics, Racial
Profiling, School Prayers. That list *is* the policy space of a stateless state in this model.

| | X | balance | GDP | Unemployment | Crime | Poverty | crises |
|---|---|---|---|---|---|---|---|
| US start | +0.573 | −$97Bn | 0.621 | 0.384 | 0.008 | 0.254 | 8 bad / 1 good |
| Ancapistan, nothing enacted | −2.131 | $0Bn | 0.170 | **1.000** | **1.000** | 0.660 | **15 bad / 0 good** |
| Ancapistan, laws optimised | −2.130 | $0Bn | 0.171 | 1.000 | 1.000 | 0.660 | 15 bad / 0 good |

Unemployment and crime both **peg at their maximum**, GDP falls to a quarter, and fifteen harmful
crises fire at once (Armed Robbery, Street Gangs, Inner City Riots, Vigilante Mobs, Contagious
Disease, Hospital Overcrowding, Technology Backwater…). X lands at −2.13 against a floor of −3.

The sharper finding is the third row: **optimising all twelve free laws moves X by 0.001.** Stripped
of money, policy is inert here — the levers that remain cannot reach the outcomes.

### Does the model give private provision a fair hearing?

Partly, and it is worth being precise rather than triumphant. Democracy 3 *does* carry explicit
private-provision nodes, and one behaves exactly as the position predicts:

| | US start | ancapistan |
|---|---|---|
| Private Pensions | 0.403 | **0.585** ← the market does step in |
| Private Schools | 0.651 | 0.585 |
| Private Housing | 0.711 | 0.485 |
| Wages | 0.411 | 0.190 |
| Productivity | 0.672 | 0.287 |

Private pensions rise when the state pension goes; private schools and housing *fall*, because in this
model private provision scales with ability to pay, and the collapse in wages and productivity removes
it. That is a coherent mechanism, not a thumb on the scale.

But **the model cannot represent the mechanism the position actually rests on**, and the shape of the
gap is specific. It is not that private-sector policies are missing — there are fifteen of them:
Healthcare Vouchers, School Vouchers, School and Health Tax Credits, Private Prisons, Agriculture and
Organic Farming Subsidies, Rural Development Grants. **Every single one is state-funded.** Not one
costs nothing, so zero revenue deletes the entire privatisation toolkit by construction.

So the model can express *the state buying private provision* — vouchers, contracting out, subsidised
markets — and cannot express *provision arising because the state withdrew*. There is likewise no node
for private security, arbitration or law. When crime pegs at 1.000, that is in large part the
simulation having no vocabulary for the position's own answer to crime, not a finding that the answer
fails. This is a **structurally unfair test**, and the run should be read as *what Positech's model
says*, not as evidence about the world. The same caution applies to every ideological scenario the
bench can run, in both directions — the useful question about any of them is first "can this model
even represent the mechanism being claimed?" 

The voter reaction is the genuinely surprising part, and it is not the expected one:

```
Capitalist    +0.140 -> +0.110      Poor           +0.874 -> -0.421
Wealthy       +0.129 -> +0.040      Socialist      -0.311 -> -0.953
Middle Income +0.045 -> +0.370      Conservatives  +0.561 -> -1.000
```

**Capitalists and the wealthy are *less* happy under zero taxation**, because the objective collapse
outweighs the tax relief; conservatives go to the floor as law and order disintegrates. Middle Income
is the only group that gains. Whatever else the model encodes, it does not simply hand the win to the
constituency that wanted the policy.

### The bug this turned up

`slp_optimize(policies=[...])` is meant to restrict which policies may *move*. It was building its
working vector from that subset alone, which deleted every other policy from the state — so the first
effect formula that referenced one by name (`StateSchools`) failed to resolve and the run crashed.
Restricting what may move is not the same as restricting what exists. Fixed in both `slp_optimize`
and `gradient_optimize`; the parameter had never been exercised before this run.

## There is no Laffer curve in the solver, and there should be

Sweeping all 25 tax policies together from 0 to 1:

```
tax level    income      GDP   TaxEvasion   Unemployment
     0.00        $0B   0.552        0.300          0.426
     0.30     $2565B   0.589        0.407          0.346
     0.60     $4428B   0.285        0.788          0.502
     1.00     $6876B   0.000        1.000          0.681
```

Revenue rises **monotonically to $6,876Bn while GDP reaches 0.000**. You cannot collect $6.9 trillion
from an economy that no longer exists, so this is a defect, not a finding about taxation.

Cause: the same economy-blindness as on the cost side, and worse here.
`AnchoredBudget.income(self, name, setting)` takes **no state argument**, so every tax already enacted
in the save — the large ones — scales with the slider alone. At 100% taxation with GDP at zero,
**$4,728Bn of the $6,876Bn comes from anchored taxes that never see the collapse**; only the $2,148Bn
from CSV-estimated taxes responds at all.

The mechanism is present in the shipped data and simply discarded. `IncomeTax` carries
`GDP,0.5+(0.5*x);TaxEvasion,1.0-(0.2*x)` — a factor of 0.744 at a healthy economy against 0.400 at a
dead one — and `notes/grammar.md` already states *"Higher rates raise TaxEvasion → diminishing revenue
(built into the data)."*

**Consequence, and it is a blocker rather than a blemish:** the solver currently cannot report that
any configuration is unaffordable, because revenue is effectively unbounded. Every "can we fund this?"
question returns yes. The fix and the plan that depends on it are in
[`notes/private-provision-design.md`](private-provision-design.md).

