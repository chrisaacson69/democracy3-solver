# Democracy 3 simulation data — CSV grammar

> Grounding notes for the parser. Source of truth: the game's own files at
> `<install>/data/simulation/*.csv`. This file documents the grammar as *observed* in the shipped
> data (Positech Democracy 3). When the parser and this doc disagree with the CSVs, the CSVs win —
> re-derive, don't guess.

## The model in one paragraph

Democracy 3 is a **data-driven feedback network**. Nodes are *simulation values*, *policies*,
*voter groups*, and *situations*. Every node emits **effects** on other nodes. An effect is a
polynomial-ish function of the source node's current value `x` (normalized to its [min,max]),
optionally lagged by an **inertia** (turns to reach full strength). The turn update resolves the
whole network toward a fixed point; the objective (vote share) is read off the voter groups.

## Row format

All files are `#`-delimited pseudo-CSV: column 1 is a literal `#` marking a data row (header rows
omit it). Fields may be quoted (descriptions contain commas). Trailing empty columns pad every row
to a fixed width and are ignored.

### `simulation.csv` — derived values (40)
```
#, name, guiname, description, zone, def, min, max, emotion, icon, #, <inputs...>, #, <outputs...>
```
- Two `#` section markers split **inputs** (effects *into* this node) from **outputs** (effects this
  node exerts on others). Either list may be empty.
- Each effect token: `Target, formula [, inertia]`.
- `def/min/max`: default value and clamp range. `emotion`: HIGHGOOD | HIGHBAD | UNKNOWN | HIDDEN.

### `policies.csv` — decision variables (~130)
```
#, name, guiname, slider, description, flags, introduce, cancel, raise, lower, department,
   mincost, maxcost, costmultiplier, implementation, minincome, maxincome, incomemultiplier,
   #Effects, <effects...>
```
- `slider`: which slider type (see `sliders.csv`) — sets discretization / display.
- `flags`: e.g. `UNCANCELLABLE`, `MULTIPLYINCOME`.
- Cost model: `mincost..maxcost` (political capital / cash), optionally scaled by `costmultiplier`
  (a `Factor,formula` list). `implementation`: turns to take effect.
- Income model (taxes): `minincome..maxincome`, scaled by `incomemultiplier`.
- `#Effects` literal marks the start of the effect list. Each effect: `Target, formula [, inertia]`.

### `votertypes.csv` — voter groups (21) — the objective
```
#, name, guiname, plural, image, overriden joins, default, percentage, desc, color, #, <influences...>
```
- `percentage`: population share (membership weight). `default`: baseline happiness bias.
- `influences`: `OtherGroup, weight` — cross-membership (a socialist is also partly a trade unionist).

### `situations.csv` — emergent states (threshold-triggered → the integer/logical layer)
Similar effect-list shape; nodes switch on/off past thresholds. (Parsed later.)

## Effect formula language

`formula` is an arithmetic expression evaluated against the current state:
- `x` = the **source node's** current normalized value.
- Operators: `+ - * /`, `^` (power), parentheses. Whitespace is insignificant.
- Bare identifiers other than `x` are **references to other nodes' values** used as multipliers.
  Rare in practice: only `*CarUsage`, `*Narcotics` appear. This is what makes the system coupled
  (not just per-node) and strictly nonlinear.
- Examples: `-0.2+(0.4*x)`, `0.98*(x^4)`, `0.30*(x^0.6)+0.07`, `(0.025+0.035*x)`,
  `0.25*(x^5)*Narcotics`.
- **Inertia** (optional 3rd field, an integer): the influence uses the **moving average of the source
  value over that many turns**, not its current value (per the manual, p6). Absent / 0 = instant.
  *At equilibrium the moving average equals the current value, so inertia does not change the steady
  state — it only affects the transient path. Phase-1 (equilibrium) can ignore it entirely.*

### Multi-part cost/income multipliers
`incomemultiplier` / `costmultiplier` are `;`-separated `Factor,formula` pairs, e.g.
`GDP,0.5+(0.5*x);TaxEvasion,1.0-(0.2*x)`. `_default_,k` sets a constant base term.

## Combination rule — CONFIRMED empirically (2026-08-10)

Validated against the game's own save (`autosave.xml`, US start, v1.34) via a single-step fixed-point
consistency check (`scripts/check_combination.py`):

```
node_value = clamp( default + Σ influenceᵢ ,  min, max )
```

- Each `influenceᵢ = formulaᵢ(source value)` (inertia-averaged; = current value at equilibrium).
- **default is added as a constant term**, not just an initial value: H1 `default+Σ` gave mean abs
  err **0.11** vs H2 `Σ only` **0.34**; many nodes matched to <0.02 (`OilPrice` exact).
- Residuals localize to (a) nodes fed by **active situations** (see below) not yet in the edge index —
  e.g. CrimeRate 0.82 (4 active crime situations), Health 0 (5 active health situations clamp it to
  the floor); (b) exogenous globals `_globaleconomy_` / `_year`; (c) inertia lag on turn-1 values not
  yet converged (e.g. CurrencyStrength reads last turn's GDP).

**Edge direction gotcha (corrected):** in `simulation.csv` a token in the *inputs* section names the
**source** (`Source→thisNode`); a token in the *outputs* section names the **target**
(`thisNode→Target`). Voter groups turned out to be almost purely **sinks** — sim-value equilibria
barely read them — so the outcome network is largely self-contained (good: matches the "voting is out
of scope" decision).

**Situations are part of the network.** `situations.csv` nodes emit effects onto sim values (e.g.
`InternetCrime→CrimeRate`, `Obesity→Health`). A situation is a node with its own value + `start`/`stop`
hysteresis triggers (0.6 / 0.4); when active it contributes like any other source. Must be loaded into
the edge index for high-connectivity nodes to resolve.

## Special / reserved node names

| Token | Meaning |
|---|---|
| `_All_` | applies to every voter group |
| `_default_` | constant base term in a multiplier list |
| `_LowIncome` `_MiddleIncome` `_HighIncome` | real sim nodes (effective income by band) |
| `_global_socialism` `_global_liberalism` | global political-mood accumulators |
| `_globaleconomy_` | exogenous global economic cycle |
| `_year` | exogenous time driver |
| `_security_` | derived security index |
| `_Terrorism` | hidden sim node |
| `<group>_freq` `<group>_income` | voter-group sub-attributes (turnout frequency, income) |

## Known data-quality issues in the shipped CSVs (do not "fix" silently — report)

Six malformed effects, all found by the loader on the first run (out of ~1000 effects):

| Policy | Raw | Problem | Intended |
|---|---|---|---|
| `ChildBenefit` | `Equality,0.0.5+(0.15*x)` | bad number `0.0.5` | likely `0.05+(0.15*x)` |
| `DeathPenalty` | `Religious-0.06-(0.06*x)` | missing comma after target | `Religious,-0.06-(0.06*x)` |
| `ForeignAid` | `Liberal,0+0.10*x)` | unmatched `)` | `Liberal,0+0.10*x` |
| `LabourLaws` | `Wages,-0.12+0.24*x)` | unmatched `)` | `Wages,-0.12+0.24*x` |
| `FoodStamps` | `Socialist,0.02+0.08*x)` | unmatched `)` | `Socialist,0.02+0.08*x` |
| `RecreationalDrugsTax` | `LegalDrugConsumption,-0.1*(x^2))` | unmatched `)` | `LegalDrugConsumption,-0.1*(x^2)` |

The loader **collects and surfaces** these in `GameModel.problems`, never fabricating a value to keep
going (grounding rule: a failed parse is not data). Four are trivially recoverable (extra `)`), one is
a missing comma, one is a number typo. If we ever apply repairs they go through an *explicit, logged*
repair pass — not a silent fix in the parser.
