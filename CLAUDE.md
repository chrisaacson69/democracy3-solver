# democracy3-solver — app-local rules

Governed by the **kernel** (`~/.claude/CLAUDE.md` — grounding + how-Chris-works) and the **project
SDK** (`Vault/projects/CLAUDE.md`). This file only adds what's specific to this repo.

## What this is

Extract Democracy 3's simulation model from its shipped CSVs, rebuild the equilibrium as a faithful
simulator (Layer 1, the oracle), then optimize policy vectors on top (Layer 2: LP/MILP). See
[README](README.md) and [`notes/grammar.md`](notes/grammar.md).

## Grounding rules specific to this repo

- **The game CSVs are the single source of truth.** Read them in place (`config.toml` → `sim_dir`);
  never copy them into the repo, and never hand-edit a value into the model. If the model and the
  CSVs disagree, the CSVs win — re-derive.
- **A failed parse is not data.** The loader records every malformed row in `GameModel.problems`.
  Do not silently "fix" the 6 shipped typos in code; if we apply repairs, they go through an
  explicit, logged repair pass that reports exactly what changed (see `notes/grammar.md`).
- **The simulator is the verifier.** Every optimizer candidate must be scored by Layer 1. Validate
  Layer 1 itself against an *independent* oracle — the game's `data_dump/inputs|outputs` debug hook
  and real playthroughs — not against a second copy of our own math (verification-independence).
- **Classify before coding.** This is a nonlinear fixed-point system with a small combinatorial part
  (discrete sliders, situation on/off). That classification, not habit, dictates solver choice.

## Harvest back to the vault

Confirmed results / reusable patterns flow UP to the vault (a topic memory + area-index pointer, or a
`research/` page) with this repo as the dated specimen — don't let findings die here. Register the
project in `Vault/INDEX.md` and keep the pointer page `Vault/projects/democracy3-solver.md` current.
