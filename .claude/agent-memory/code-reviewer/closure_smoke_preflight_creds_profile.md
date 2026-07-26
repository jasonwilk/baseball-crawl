# Step 1d closure smoke: a red mobile creds profile is NOT a preflight fail

`bb creds check` audits BOTH a "web" and a "mobile" profile and ALWAYS prints the mobile block dead — mobile has no programmatic refresh, because the client key is not extractable from the iOS binary. The reports/scouting path (`bb report generate`, `morning-run`, boxscore fetch) uses the WEB profile EXCLUSIVELY (a bare `GameChangerClient()` resolves to `profile="web"`). So a red mobile block is expected output, not a broken environment. Confirm the WEB profile is live (API Health `GET /me/user` → 200) before declaring an ENV-FAIL on credentials.

This is why the Step 1d preflight specifies `bb creds check --profile web` rather than the bare multi-profile form: the bare form exit-0-PASSES on a mixed state where a valid mobile profile masks a dead web one, which is the failure this check exists to catch.

## Retired 2026-07-26: the stale-baseline drift adjudication

This file previously carried a four-step procedure for adjudicating a `bb report reconcile-scoreboard` exit-1 during Step 1d — the recurring case where the live dev DB had accumulated games far beyond the committed baseline snapshot, so absolute counters read as "regressions" that were pure data-volume artifacts (E-261: baseline 213 games @ 2026-07-12 vs live 405). **The one-way ratchet gate was retired on the operator's decision that it cost more attention than it returned, and that procedure retired with it.** Step 1d now asserts only `self_games == 0` from `--json` and ignores the command's exit code entirely, so the drift artifact can no longer reach you as a FAIL to adjudicate.

Two things carry forward. `self_games == 0` remains a hard zero and a real invariant — volume-independent, and the place a genuine dedup or perspective bug shows up. And the underlying lesson outlives the ratchet: **a comparison against a stored snapshot degrades silently as the thing it snapshots grows**, and its first symptom is a confident FAIL with a plausible number behind it. See [[worktree_pytest_loads_the_worktree_src]] for the sibling "the closure signal isn't what it looks like" lesson.
