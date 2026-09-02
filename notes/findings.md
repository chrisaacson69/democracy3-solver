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

## Which crises are traps? Almost none — 24 of 27 clear themselves

The transition worry is that a route to a good destination might dip through a crisis and, because
hysteresis makes crises cheaper to cause than to clear, get stuck there. The tempting workaround is to
switch crises off during the transition and back on afterwards. **Don't** — that experiment has already
been run by accident: the SLP with `freeze_active=True` reported `X = 3.000`, and the identical policy
vector with the crises released was **2.788 at −$42Bn, infeasible**. Freezing does not neutralise a
crisis, it hides it until you stop looking.

The answerable question is narrower and much more useful: *given the destination policy set, which
crises are self-sustaining once entered?* Force each dormant crisis on, re-solve with hysteresis live,
and see whether the policy set clears it again.

Against the balanced-welfare optimum: **24 of 27 clear on their own. Three do not.**

| self-sustaining | kind | value at eq. | stop trigger | margin |
|---|---|---|---|---|
| High Productivity | **positive — a lock-in you want** | 0.519 | 0.40 | +0.119 |
| Petrol Protests | harmful | 0.523 | 0.40 | +0.123 |
| Teachers Strike | harmful | 0.445 | 0.40 | **+0.045** |

So the transition is far less fragile than expected. Only **two** harmful crises are absorbing, and
both sit close to their exit — Teachers Strike is barely stuck at all, 0.045 above the threshold that
would clear it. Everything else is a speed bump: unpleasant to pass through, but it resolves once the
policy set is in place.

Three consequences for planning a route:

1. **Turning crises off is unnecessary as well as unsound.** The dust really does settle by itself for
   24 of 27. The constraint is not "never enter a crisis", it is "never enter *these two*".
2. **One trap is worth falling into.** High Productivity is a positive situation that locks in once
   entered. Hysteresis cuts both ways, and a route that deliberately trips it is a route worth taking.
3. **A shallow trap is a budget line, not a wall.** Teachers Strike needs 0.045 of movement to clear.
   That is a cost to price against the alternatives, not a hard constraint — exactly the kind of thing
   `scripts/cost_effectiveness.py` can rank.

Method note: reversibility is a property of the *destination policy set*, not of the crisis. A
different endpoint will produce a different trap list, so this test belongs in route planning, run
against whatever destination the joint solve returns — not cached as a fact about the game.

## Income elasticity fixed — and the wall is not revenue, it is the economy

`AnchoredBudget` now carries the CSVs' state elasticity as a ratio about the anchor point:

```
income(n, s, state) = i0 * (s/v0) * k * [ mult(state) / mult(anchor_state) ]
```

Evaluated at the **anchor's own setting** in both numerator and denominator, so it captures state
movement only — using the current setting would double-count the `s/v0` scaling already applied, and
for a policy whose multiplier names an undefined node (`Poor_perc`, where `x` falls back to the
setting) that error would have been silent.

The reference state is the **equilibrium** of the anchor policy vector, not the save's raw
`sim_values`. The save is a turn-1 transient, so anchoring to it made the ratio differ from 1.0 at the
very point the anchors were calibrated for, shifting the US start's balance from −$97.00Bn to
+$49.19Bn. With the equilibrium as reference the balance is **−$97.000Bn both before and after**: the
regression test that says no previously reported number moved.

### The sweep, before and after

| tax level | before | after | GDP | TaxEvasion |
|---|---|---|---|---|
| 0.30 | $2,565Bn | $2,516Bn | 0.589 | 0.407 |
| **0.50** | $3,996Bn | **$3,599Bn** | 0.492 | 0.622 |
| 0.60 | $4,428Bn | **$3,459Bn** ↓ | 0.285 | 0.788 |
| 1.00 | $6,876Bn | $4,019Bn | **0.000** | 1.000 |

Peak revenue falls **42%**, and a real local peak appears at 0.50 with a dip through 0.60 — revenue
now *falls* as the economy contracts, which it could not do before.

### But there is still no full Laffer curve, and that is the game's doing

Revenue climbs again past 0.8. Two causes, and only one of them is ours:

1. **The shipped multipliers are weak.** At total collapse Income Tax keeps **55%** of its revenue
   (`GDP,0.5+(0.5*x);TaxEvasion,1.0-(0.2*x)` — evasion caps at a 20% haircut) and Sales Tax keeps 26%.
   Against a rate rising 0.34 → 1.00, that is not enough to turn the curve over. **Democracy 3 does
   not model a revenue-maximising tax rate**, and no amount of fixing on our side will invent one.
2. **The anchored form extrapolates.** `s/v0` is unbounded, so Property Tax at an anchor of 0.11 is
   extrapolated **9.1×** at s = 1.0. Trustworthy near the anchor, increasingly speculative away from
   it. The largest revenue line at s = 1.0 — Flat Income Tax at $1,358Bn — is not anchored at all and
   comes entirely from the CSV path.

### What this means for minimal taxation

**Revenue is not the binding constraint.** At the sensible operating limit — tax 0.50, where GDP is
still 0.492 — revenue is **$3,599Bn against current spending of $1,288Bn**, roughly 2.8× headroom.
Past that the economy is dead and the revenue figures are arithmetic rather than policy.

So the ">100% tax rate" worry does not bite in this model. What bites first is GDP collapse and the
crisis thresholds that come with it. Any "tax only enough to fund it" exercise should be constrained
by *where the economy still works*, not by where the money runs out.

## The tax dial: how good can the country be at each level of taxation?

`scripts/tax_frontier.py` pins taxation, lets the optimiser spend what that raises however it likes
subject to `balance >= 0`, and records the country that results. Rows marked * were re-solved from
three starts after the single-start pass failed on them (see the method note below).

|  tax | income | spend | balance | X | GDP | Unemp | Poverty | Crime | Health | Equality |
|---|---|---|---|---|---|---|---|---|---|---|
| US start, **unoptimised** | $1222B | $1276B | −$54B | **+0.573** | 0.621 | 0.384 | 0.254 | 0.008 | 0.379 | 0.218 |
| 0.20 | $244B | $244B | $0B | +1.294 | 0.587 | 0.548 | 0.161 | 0.000 | 0.938 | 0.479 |
| 0.40 * | $486B | $486B | $0B | +1.625 | 0.588 | 0.521 | 0.024 | 0.000 | 0.880 | 0.702 |
| 0.60 | $742B | $742B | $0B | +1.187 | 0.621 | 0.437 | 0.143 | 0.000 | 0.779 | 0.367 |
| 0.80 | $1036B | $871B | +$165B | +1.715 | 0.699 | 0.320 | 0.109 | 0.000 | 1.000 | 0.445 |
| **1.00 *** | $1306B | $1217B | **+$89B** | **+1.913** | 0.730 | 0.221 | 0.122 | 0.000 | 0.982 | 0.544 |
| 1.20 | $1574B | $1574B | +$1B | +2.447 | 0.753 | 0.000 | 0.000 | 0.000 | 1.000 | 0.694 |
| 1.40 | $1923B | $1887B | +$36B | +2.687 | 0.856 | 0.000 | 0.000 | 0.000 | 1.000 | 0.831 |

Three readings, in order of how much they matter.

**1. Reallocation alone is worth more than any tax change.** At *unchanged* taxation, simply spending
the money better takes X from **+0.573 to +1.913** and turns a −$54Bn deficit into a **+$89Bn
surplus** — while spending slightly *less* ($1,217Bn against $1,276Bn). Health 0.379 → 0.982, poverty
0.254 → 0.122, unemployment 0.384 → 0.221, crime to zero. Before any argument about the size of the
state, the current one is leaving most of its own budget's value on the table.

**2. You can run at 40% of current taxation and keep 85% of the achievable welfare.** Tax 0.40 reaches
X = +1.625 against the fully-funded +1.913, on **$486Bn instead of $1,217Bn** — and it is *better* on
poverty (0.024 vs 0.122) and equality (0.702 vs 0.544). The cheap outcomes really are cheap.

**3. Employment is the entire cost of a small state.** It is the one column that does not come cheap:
0.221 at full taxation against 0.521 at 0.40× and 0.548 at 0.20×. Health, poverty, crime and equality
are all purchasable at a fifth of the budget; jobs are not. This is the military-as-jobs-programme
finding arriving from the opposite direction, and it is the sharpest target the private-provision work
has: **an invented REA adds least on health or crime, and most on employment.**

### Method note: single-start local search was unreliable here

The first pass produced two rows that dipped below both neighbours *and* missed the balance
constraint. A monotone curve should not have holes, and those holes were the optimizer failing rather
than the world being strange — tax 0.40 read X = +0.774 when +1.625 was available, a 2× error.

Re-solved from three starting points (as-is, all-spending-zero, all-spending-one), both recovered. The
spread at tax 1.00 is the warning worth keeping: **X = +1.913, +1.909 and +0.047** from the three
starts. The last is a perfectly valid local optimum and a useless answer. `tax_frontier.py` now
multi-starts by default.

One more trap this run walked into: the first corrected attempt optimised with `freeze_active=True`
and re-scored with `False`, and *every* row came back infeasible. Now that the budget carries state
elasticity it is **basin-dependent**, so optimising and scoring in different basins silently breaks the
constraint the optimiser thought it had satisfied. Optimise and report in the same basin.

## Can state-funded *private* provision alone fix ancapistan? Health yes, crime no

From a blank slate, adding only the policies that fund private provision (plus taxes to pay for them),
optimised for the welfare basket:

| scenario | X | spend | balance | GDP | Unemp | Poverty | **Crime** | Health | Equality |
|---|---|---|---|---|---|---|---|---|---|
| Ancapistan, nothing at all | −2.131 | $0B | $0B | 0.170 | 1.000 | 0.660 | **1.000** | 0.260 | 0.099 |
| + the 12 free laws only | −1.623 | $0B | $0B | 0.483 | 0.810 | 0.465 | **1.000** | 0.153 | 0.016 |
| + private provision + taxes | −0.588 | $645B | **+$807B** | 0.324 | 0.816 | 0.487 | **1.000** | 0.560 | 0.831 |
| + private + free laws + taxes | −0.194 | $628B | **+$1402B** | 0.381 | 0.748 | 0.470 | **1.000** | 0.645 | 0.998 |
| + everything (all 123) | +2.898 | $5314B | +$458B | 0.898 | 0.000 | 0.000 | **0.000** | 1.000 | 1.000 |

**Only four policies fund private provision**, and they cover exactly two domains: `HealthcareVouchers`
and `HealthTaxCredits` push `PrivateHealthcare`; `SchoolVouchers` and `SchoolTaxCredits` push
`PrivateSchools`. Nothing funds private pensions — `PrivatePensions` rises only when `StatePensions`
falls, a crowding-in effect with no lever of its own — and `RentControls` carries
`PrivateHousing −0.1−(0.15*x)`, so it *suppresses* private housing rather than funding it.

What private provision achieves: **equality 0.099 → 0.831** (solved) and **health 0.260 → 0.560**
(materially improved). What it does not touch: **crime stays pegged at 1.000**, unemployment 0.816,
poverty 0.487.

**Crime is the failure, and it is total.** The intuition going in was that employment would be the
gap; employment *is* a gap, but crime is worse — it does not move at all, from any private
configuration, because the model contains **no privately-provided law enforcement**. `PrivatePrisons`
exists but merely runs incarceration the state has already ordered; there is no private policing,
arbitration or rights enforcement to fund.

The tell is the balance column: **+$807Bn, rising to +$1,402Bn**. The optimiser is raising money it
cannot spend, because after four voucher programmes there is nothing private left to buy. That surplus
is the size of the hole in the policy space.

**This is the precise case for inventing a Rights Enforcement Agency**, and it is a much sharper target
than "replace government functions". Crime pegged at maximum with no private mechanism available is
exactly the shape of a missing-vocabulary problem rather than a defeated argument — the same diagnosis
as the ancapistan run, now localised to one domain and one number.

A testable follow-on: crime at 1.000 is very likely *causing* much of the rest. It drags GDP, and GDP
drives unemployment at −0.700, the largest coefficient in the network. So an REA that fixed crime might
cascade into employment without employing anyone. That is a prediction the bench can check the moment
such a policy exists.

### What non-private policies actually solve employment

Two distinct routes, and they are worth telling apart:

**Direct employment** — the state as employer, coefficient on `Unemployment`:
`MilitarySpending −0.230`, `StateHealthService −0.190`, `StateSchools −0.190`,
`AgricultureSubsidies −0.170`, `RuralDevelopmentGrants −0.150`, `ChildcareProvision −0.110`,
`ImportTariffs −0.100`, `RailSubsidies −0.090`. Private provision does the same thing more weakly:
`PrivateSchools −0.130` against state schools' −0.190, `PrivateHealthCare −0.070` against −0.190.
Vouchers cost about a third of the education employment and nearly two-thirds of the health employment.

**Growth** — `GDP → Unemployment` is `0.9−(0.7*x)`, **at −0.700 the largest single lever in the
network**, three times military spending. It is raised by `Productivity +0.440`, `InternationalTrade
+0.150`, `Tourism +0.120`, and weakly by `ScienceFunding +0.08`, `TaxShelters +0.06`,
`SmallBusinessGrants +0.05`, `ForeignInvestorTaxBreaks +0.05`. It is dragged by
**`CorporationTax −0.270`** and **`CarbonTax −0.250`**, plus the `SkillsShortage −0.317` and
`CorporateExodus −0.270` situations.

So the market answer to employment is present in the data: **cut corporate taxation, raise
productivity, stay out of the Skills Shortage and Corporate Exodus basins.** The catch is that the
direct route is one strong coefficient while the growth route is a chain of weak ones — no single
GDP-raising policy exceeds +0.08. Whether the chain can beat direct hiring at equal cost is the next
thing worth measuring.

## Is the model generic? Yes — and we were running the USA slightly wrong

The question was whether a country is needed at all, given the CSVs work on a relative scale. The
answer is in three parts.

**The effect network is country-agnostic, and the feedback loops need no absolutes.** A single
`data/simulation/` serves all six countries: `simulation.csv`, `policies.csv`, `votertypes.csv` and
`situations.csv` exist once. The 1,149 edges, 40 outcomes and 36 crises are identical everywhere, and
the equilibrium solve runs entirely in the normalised [0,1] space the CSVs define — **no absolute
quantity enters it**. Absolutes (population, GDP range, income bands, `wealth_mod`) are needed only by
the *budget* layer, to turn slider positions into dollars. So a country is a **starting condition plus
a small patch**, not a different model, and a country dropdown is a real and cheap prospect.

**But there is a patch, and we were ignoring it.** `missions/<country>/overrides/*.ini` edits the
network per country:

| country | overrides |
|---|---|
| usa | deletes `HandgunLaws → ViolentCrimeRate`; adds `LuxuryGoodsTax` and `MansionTax` → `MiddleIncome` |
| uk | deletes `Gambling → Religious` |
| france | 6, incl. `StateSchools → TeachersStrike` and `StateHealthService → DoctorsStrike` |
| germany | 2 | canada, australia | none |

Loading the shared CSVs alone therefore has **handgun laws cutting violent crime in a US game whose
own scenario deletes that edge**. `loader.load_overrides` now applies them and
`loader.load_country(sim_dir, "usa")` is the front door.

**How much did it matter?** At the US start, *nothing* — X is identical to four decimals. The reason is
worth keeping: `ViolentCrimeRate` sits clamped at its floor, so the deleted edge was inert, and both
`LuxuryGoodsTax` and `MansionTax` are switched off, so their added edges contributed zero. The bug was
real and its baseline impact was nil.

It bites the moment you enact those taxes — **which the optimiser did**, recommending `MansionTax → 1.00`:

| | MiddleIncome |
|---|---|
| shared CSVs only | −0.040 |
| + USA overrides | **−0.170** |

A 4× understatement of what that recommendation costs middle incomes. The lesson generalises: a defect
that measures zero at the baseline is not harmless, it is *dormant*, and an optimiser's job is to walk
to exactly the places where dormant things wake up.

France ships a **7th data typo** on top of the six in the CSVs: `RailSubsidies → Rail Strike` has the
equation `0-(0.8*x))`, an unmatched paren. It is surfaced as a problem and the original edge survives —
never fabricated, never silently dropped.

### Still country-specific and still unread

`missions/<country>/scripts/*.txt` sets starting voter biases (`CreateGrudge(USA,_hidden_,
Religious_freq,0.33,1,0)` and eight more for the USA). Those shape the initial voter state, which the
solver currently takes from the savegame instead. Reading them, plus the mission budget constants,
is what would make the country a dropdown rather than a rebuild.

## Marginal value does not survive the journey

Chris noticed that Internet Tax tops the Atlas as the best *free* unemployment lever and does not
appear in either recipe, and asked what the recipe panel was for. Checking it produced a better answer
than the question expected, and a bug.

**Internet Tax, +0.15, evaluated from three different states:**

| starting state | change in X | balance |
|---|---|---|
| US start | **+0.0139** | +$11Bn |
| Same taxes, spent well | **0.0000** | +$12Bn |
| Two fifths of the taxes | **−0.0114** | +$15Bn |

The best free unemployment lever *from where the US actually is* is worth exactly nothing at one
optimum and is actively harmful at another. Nothing is inconsistent: the efficiency matrix ranks **the
next move from the US start**, and a recipe is a state 65–74 policy changes away. A ranking is a
statement about a point, not a property of a policy.

This is the same lesson as average-vs-marginal value from the cost-effectiveness work, arriving from a
third direction, and it is the honest limit of the Atlas: **it tells you what to do next from here, not
what belongs in a finished configuration.**

### And a defect: the recipes advertised numbers their own checklist could not produce

A checklist can only ask for two decimals, but the recipes were reporting the outcomes of the
*unrounded* optimiser vector. For "Same taxes, spent well" the drift was harmless (X +1.9126 →
+1.9177). For "Two fifths of the taxes" it was not:

| | advertised | what the checklist actually delivers |
|---|---|---|
| X | +1.6252 | **+1.3424** |
| CrimeRate | 0.000 | **0.104** |
| Health | 0.880 | **0.734** |

Rounding 74 sliders to two decimals pushed the state **across a crisis threshold** — a step, not a
rounding error, and exactly the discontinuity the Atlas flags elsewhere. Recipes are now evaluated
*after* rounding, so the advertised numbers are the ones you get by following the list. Anything that
tells you what to type has to be scored on what you would type.

## Clamped outcomes are blind spots, and the optimiser exploits them

Chris: *"the balanced version produces unemployment of 0, crime of 0 yet has black market, ghettos,
organised crime and tax evasion — that just seemed odd."*

It is odd, and it is not a display artifact. It is a defect in the objective.

At the welfare optimum, `CrimeRate` reports **0.000**. Its unclamped sum is **−0.43** — the policy suite
drives crime so far past the floor that there is 0.43 of slack below the bound. Meanwhile Organised
Crime (+0.2225) and Black Market (+0.0756) are actively pushing crime *up*; they are simply buried
under the overshoot.

So what does the objective gain by clearing them?

| clearing | change in X |
|---|---|
| Organised Crime | **−0.00000** |
| Black Market | **−0.00000** |
| Tax Evasion | **−0.00000** |
| Ghettos | +0.00475 |

**Nothing.** `CrimeRate` is pinned at its floor, so removing a crime crisis buys no movement in the one
channel the objective scores it through. `Equality` is pinned at its ceiling of 1.000, so Ghettos'
equality damage is invisible for the same reason from the other end. The crises are *free to leave
running* — not because they are harmless, but because **the metric cannot register them.**

This is the saturation problem from the Layer-2 notes, and it is worse than "the score stops being
informative". A clamped outcome does not merely stop rewarding improvement; it makes **entire
categories of damage invisible**, and an optimiser will then park real problems inside the blind spot
because they are costless there. Every objective built on clamped [0,1] outcomes has this failure mode
wherever it saturates.

Two consequences worth carrying:

1. **A saturated outcome is a warning, not a victory.** `CrimeRate 0.000` with 0.43 of slack means the
   spending past the boundary bought nothing and could have gone elsewhere — and that anything whose
   only channel is crime is now unpriced.
2. **Chris's playstyle is the right correction.** "Solve the worst crisis first" prices crises directly
   rather than through a saturable proxy. The principled version is to add an explicit term for active
   harmful crises to the objective, so they are scored even when their outcome channel is pinned.

### A method note on how this was found

The first reconstruction of `CrimeRate` gave +0.18 against the solver's 0.000 and looked like a solver
bug. It was a bug in the *analysis script*: `Equilibrium.values` holds endogenous nodes only, so
`eq.values.get(source, 0.0)` scored every **policy**-sourced edge at x = 0 — silently zeroing exactly
the crime-reducing policies under investigation. Rebuilding the state the way `solver.py` does
(exogenous + policies + node values) reproduced −0.4317 → 0.000 exactly. A discrepancy between a
reconstruction and the thing it reconstructs is evidence about *one* of them, and the reconstruction is
usually the newer and worse-tested code.

## Pricing crises directly is free — and it is a better *search*, not just a preference

The blind-spot finding above says the objective cannot see crises whose outcome channel is clamped.
The obvious correction is to price them directly: add `-lambda x value` for each of the 34 harmful
situations, leaving the welfare basket untouched. Every row below is scored on the **original**
basket, so the comparison is fair.

| lambda | welfare X | harmful crises | balance | still running |
|---|---|---|---|---|
| 0.00 | +2.898 | 9 | +$458Bn | Pollution, Asthma, Teacher Shortage, Doctors Strike, Brain Drain … |
| **0.05** | **+3.000** | **4** | −$0Bn | Pollution, Asthma, Rail Strike, Ghettos |
| 0.15 | +2.860 | **1** | −$0Bn | Rail Strike |
| 0.40 | +2.829 | 2 | −$0Bn | Doctors Strike, Tax Evasion |

**A small crisis price is strictly better on both axes.** At lambda 0.05 the welfare score *rises* from
+2.898 to +3.000 — the basket's ceiling — while harmful crises more than halve. That is not a
trade-off being made well; it is a free lunch, and it means the lambda = 0 run was simply stuck.

The reason is the blind spot itself. A clamped outcome gives the optimiser a **flat plateau**: no
gradient, so nothing to climb. The crisis values still vary there, so pricing them restores a slope in
a region where the honest objective has none. It is the same device as the trust-region merit function
— when the thing you care about stops varying, score a proxy that still does — and it is why Chris's
"solve the worst crisis first" beats a pure outcome objective rather than merely differing from it.

Past that, the trade becomes real but stays cheap: **lambda 0.15 leaves exactly one harmful crisis
running for 0.14 of X**, about 5%. And lambda 0.40 is worse on *both* counts (+2.829, 2 crises) —
over-pricing starts chasing situation values at the expense of the outcomes they were standing in for.

Two consequences:

1. **lambda ~0.05 should be the default objective**, since it dominates lambda = 0 outright. Anything
   above that is a genuine preference about how much welfare a quiet country is worth, and belongs to
   the person choosing X rather than to the solver.
2. The lambda = 0 run also hoards **+$458Bn** it never spends, while every priced run lands at −$0Bn.
   The blind objective was not just tolerating crises, it was failing to find anything worth buying —
   more evidence it had stalled on a plateau rather than reached an optimum.

