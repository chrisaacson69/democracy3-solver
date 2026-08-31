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
