# ⛔ THESE HARNESSES NO LONGER RUN AS COMMITTED — the seams they call changed at E-276

**Added 2026-07-26 by product-manager, at E-276 closure, on a code-reviewer SHOULD FIX.**

**Do not delete these files and do not "fix" them by guessing.** They are the committed record of constructions that would otherwise have existed only in a session transcript — E-276 TN-16's rule that *a construction that exists only in a transcript is not a regression test*. **That is exactly why they were committed, and it is why a silent breakage matters.**

## What broke

E-276 changed three reconcile-at-load seam signatures. **Nine call sites across four files under `recon_audit/` now raise `TypeError`** because they call the pre-epic forms:

| Seam | What changed |
|---|---|
| `retire_absent_player_lines` | gained a **required** keyword `prior_snapshots` — `{(table, team_id): frozenset(player_id)}`, captured **pre-upsert** by the caller |
| `retire_absent_games` | gained a **required** keyword `prior_snapshot` — the games loaded as of the **start of the run**, captured above the boxscore load |
| `crawl_is_authoritative` | gained `permit_empty_prior` (default `False`). **Both production callers pass `True`** |

### ⛔ FOUR FILES ARE DEAD, NOT MERELY STALE — read this before anything below

**`recon_audit/t_playerline.py`, `t_game.py`, `t_guard.py` and `t_rest.py` DO NOT RUN AT ALL.** They raise `TypeError` on the new required parameters, at the call, before producing any output. **They are broken, not inaccurate.**

**⚠️ An earlier version of this file got that wrong, and the error is instructive enough to record rather than quietly fix** *(corrected 2026-07-26, same day, on a second code-reviewer finding)*. The first draft described every breakage as *"modelling something stale"* and **listed `t_rest.py` among files that "raise nothing" — it does raise.** A reader could have taken the whole header as *"these measure a superseded design"* and never learned that four of them are dead. **The advice further down about supplying new parameters is only relevant once you know the file does not execute at all.**

### One file is STALE BUT STILL RUNS — the worse failure mode of the two

- **`e276-review/x_attack.py`** calls `crawl_is_authoritative` **without** the opt-in. **It executes and prints results**, and now models **the default path no production caller uses.** Nothing in its output signals that its subject is a configuration that does not ship. **A dead file announces itself; this one does not.**

**`recon_audit/t_rest.py` belongs to BOTH categories**: it raises on the new signatures, *and* the roster floor it exercises was **removed entirely** by E-276-03 — so even repaired it would measure a design that no longer exists.

## Why this is recorded rather than repaired

**Repairing them would mean re-running them**, and their value is as a record of what was executed *at the time*, against the code as it then stood. **A harness edited to pass against today's code is no longer evidence about the audit.** So: the calls are left as they were, and this header is the correction.

**⚠️ Stories E-276-01 and E-276-02 cite files in this directory BY NAME in their Technical Approach as reproduction sources.** A reader following those citations gets a `TypeError`, not a reproduction. **Read them as historical artifacts**: the constructions and their printed results are the deliverable; the call syntax is stale.

## If you need to actually run one

Supply the new parameters from the current signatures in `src/db/reconcile_at_load.py` — **and understand that you are then running a NEW experiment, not reproducing the audit's.** The gate population changed, which is the whole subject of E-276; a harness fed a pre-upsert snapshot will not reproduce a pre-epic result and should not be expected to.

## Provenance

Committed at `ee95a31`, **before** E-276 — zero `fable-audit` paths appear in E-276's staged diff, so **nothing in this epic edited them.** They are not collectible by pytest (no `def test_` in any of the ten files, none named `test_*.py`) and are not imported or path-referenced anywhere in `src/`, `tests/` or `scripts/` — which is why this was a SHOULD FIX rather than a MUST, and why the breakage is silent.

**The transferable point, and the reason this file exists**: an epic's own evidence base can go stale without a single test failing, and **the sweep that catches retired prose claims does not catch stale call sites in the same tree.** Same directory, different property, two different instruments.
