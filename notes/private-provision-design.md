# Design note: private provision, minimal taxation, and the order to do it in

> Chris, 2026-08-31: *"next trick is to implement the private policies and only charge enough tax to
> support them… bad economy feedback could mean >100% tax rates, and I don't know if we should be
> implementing them as needed or all at once."*
>
> Three questions in there. The third has a clean answer, the second has a cleaner answer than
> expected, and the first has a prerequisite that has to land before either matters.

## 0. The prerequisite: the revenue side cannot currently price anything

**Do this first or the rest is meaningless.** Sweeping all 25 tax policies from 0 to 1 produces
revenue that rises monotonically to **$6,876Bn — while GDP sits at 0.000 and TaxEvasion is pegged at
1.000.** You cannot collect $6.9 trillion from an economy that no longer exists.

The cause is the same economy-blindness `notes/layer2.md` records on the cost side, and it is worse
here. `AnchoredBudget.income(self, name, setting)` takes **no state argument**, so for every tax
already enacted in the save — which is the big ones — revenue scales with the slider alone:

```
at 100% taxation, GDP 0.000, TaxEvasion 1.000:
   $4,728Bn from ANCHORED taxes   <- ignores the collapse completely
   $2,148Bn from CSV-estimated    <- these do respond
```

The Laffer mechanism **is in the shipped data**: `IncomeTax` carries
`GDP,0.5+(0.5*x);TaxEvasion,1.0-(0.2*x)`, worth a factor of 0.744 at a healthy economy and 0.400 at a
dead one. `notes/grammar.md` even says so — *"Higher rates raise TaxEvasion → diminishing revenue
(built into the data)."* The anchored path discards it.

**Recommended fix — cheap, and a conversion rather than an invention.** Keep the anchor for the
*level* and take the *shape* from the CSVs, as a relative adjustment about the anchor point:

```
income(n, s, state) = i0 * (s / v0) * k * [ mult(state) / mult(state_anchor) ]
```

At the anchor state the bracket is 1.0, so every number this project has already reported is
unchanged; away from it, revenue gains the GDP and TaxEvasion elasticity the game intends. Same
treatment for `AnchoredBudget.cost`. This is strictly less work than full CSV grounding and it
restores the feedback that the whole "minimal taxation" question depends on.

## 1. ">100% tax rates" — the model reports this as infeasibility, not as a silly number

Policy sliders are bounded `[0,1]`, so the model has no way to *express* a 150% tax rate. What "we'd
need more than 100%" means here is that **no policy vector satisfies `balance >= 0`** — and that is a
question with a rigorous answer rather than a runaway number.

This is the one place the MILP earns its keep over the SLP. A local search that fails to find a
feasible point tells you nothing (maybe it looked in the wrong place); **the MILP either returns a
feasible vector or proves none exists.** So the right shape for the question is:

> Fix the private-provision policies at the levels you want. Ask the MILP to satisfy `balance >= 0`.
> Infeasible ⇒ the configuration genuinely cannot be funded at any tax rate the game permits.

With the fix in §0 that becomes a real test, because revenue will finally be bounded by the economy.
**Right now it would always report feasible**, since revenue is effectively unbounded — the model
cannot currently tell you that anything is unaffordable.

Worth expecting: the binding constraint may not be revenue at all. Taxation feeds
`TaxEvasion`, `GDP` and the voter groups, and a high-tax equilibrium can trip crisis thresholds well
before it runs out of money.

## 2. As-needed or all at once? Both, for different questions

They are not competing answers, they are answers to different questions, and the project already has
the machinery for each.

**All at once — for the destination.** Policies interact: a private-schooling policy moves GDP, which
moves tax revenue, which changes what else is affordable. A sequential greedy cannot see that and
provably cannot beat a joint solve; `refine_milp` does the joint solve natively and treats the whole
configuration as one problem. Use it to find *what the end state should be*.

**Sequenced — for the route.** And here the transition is not a formality, because of a property this
project has already measured: **crises are far cheaper to cause than to clear.** Hysteresis means a
crisis switches on above its start trigger but only off below a *lower* stop trigger, so a transition
that dips across a threshold on the way can strand you in a basin the endpoint analysis says is fine
but which you can no longer reach from. Cutting public provision before private provision has ramped
is exactly the shape of move that does this.

So the rule is concrete: **plan the destination jointly, then order the moves so the path never
crosses a crisis threshold.** `scripts/cost_effectiveness.py` already ranks moves by value, and the
bench's sweep already finds the exact level at which each crisis flips — that is the constraint the
ordering has to respect. This is `notes/scope.md`'s Phase 2 ("*how to actually get there*"), which was
always in the plan.

A useful diagnostic falls out of it: if the destination is reachable **only** by passing through a
crisis, that is worth reporting as its own finding rather than buried in a move list.

## 3. Inventing the policies at all — keep the provenance visible

Everything in this project so far is a *conversion* of Positech's shipped data, which is what lets any
result be checked against the game. Adding private-provision policies that the game does not have
crosses that line: the model becomes partly ours, and "the model says X" stops meaning what it meant.

That is a legitimate thing to want — it is counterfactual modelling, and §2 of `notes/findings.md`
shows why it is *needed* here, since every one of the game's fifteen privatisation policies is
state-funded and none can exist at zero revenue. But it should be structurally separated, not mixed in:

- **Keep invented policies in an overlay** (`mods/private_provision.csv`), same grammar, loaded on top
  of the shipped data rather than edited into it. The `raw/`-immutability instinct from the vault
  applies: the shipped data is the source of truth and stays untouched.
- **Tag provenance per effect.** `Effect` gains a `source` field (`shipped` | `overlay`), and any
  result can then report "N of M contributing edges are invented" — the same honesty discipline as
  `max_pwl_error` and the anchored/estimated split already in use.
- **Derive the formulas by analogy, not by taste.** The defensible way to write a *Private Police*
  effect curve is to take the structural relationship an existing pair already encodes — the way
  `StateSchools` relates to `PrivateSchools`, or how `PrivatePensions` rises when `StatePensions`
  falls — and transfer it. That is a conversion with a citable source. Numbers picked because they
  feel right are the thing the project's first rule exists to prevent.
- **Always be able to run vanilla.** Overlay off must reproduce today's numbers exactly; that is the
  regression test that the overlay changes only what it claims to.

## Suggested order

1. **Fix `AnchoredBudget` income and cost to take state** (§0). Without it nothing downstream prices
   correctly, and the anchor-relative form means no existing result moves.
2. **Re-run the tax sweep** and confirm a revenue ceiling actually appears. That is the check that §0
   worked.
3. **Build the overlay mechanism** with provenance tagging and a vanilla-equivalence test, before
   writing a single invented policy.
4. **Then** write the private-provision policies, by analogy, a few at a time.
5. **Ask the MILP for the destination**; ask the sweep for a route that clears no crisis threshold.
