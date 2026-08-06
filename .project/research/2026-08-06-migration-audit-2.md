# Migration Audit 2 — chunks 4–6 of the single-agent flow

Date: 2026-08-06. Covers chunks landed 2026-08-04 through 2026-08-05.
Prior: `2026-08-04-migration-audit-1.md`.

## Scorecard

| chunk | commits | escaped defects | process notes |
|---|---|---|---|
| 4. CI fix (pip 26.2 pin + crypto advisory) | ca3b852, 04efd99 | 0 | Cleanest round of the migration: lifecycle steps announced, positive controls on everything (proved a mocked-green suite CAN fail), first honored /clear-and-resume |
| 5. Entity-class filter (orgs ≠ teams) | a87f9d0 → b9bc37f, 6cafdc5 | 0 | Proper handoff + clear between plan and execute; caught the agreement changing mid-session and re-read; refused a pass wearing an INCONCLUSIVE gate line |
| 6. Rung-c auto-accept fix | b8db263 (+1274/−87, 15 new tests) | 0 | Operator deliberately rode the same session past 500k ("not clearing") — worked, but is the exception that needs to stay one |

Quality: zero escaped defects in six chunks. Review chains keep catching
author-blind claims (a false "only two paths" claim contradicting the
author's own cited measurement; a HIGH where correcting a mapping did not
correct the report). The defect layer has MOVED: execution is clean, the
failures are framing — context-free questions to the operator, stubs born
from unverified premises, no product awareness. All three operator
complaints of 2026-08-06 substantiated from transcripts.

## Lesson routing (hook/test > agreement line > memory > drop)

| lesson | evidence | route |
|---|---|---|
| Bash writes bypass every write guard (cp/mv/redirects invisible to hooks) | bitten twice (org-probe cp; api-scout block) | AGREEMENT — appended to principle H this audit |
| A cited claim is a claim: 3 of 6 stubs were inherited-premise failures, not discoveries | post-search-name-year (load-bearing doc line contradicted by repo data), harvest-web-bundle (450 guess-probes when the JS bundle listed the API), season-year filter (shelved on a refuted premise) | AGREEMENT — step 1 now requires verifying load-bearing citations |
| Questions must be operator-shaped | "I don't have enough context" + "sorry. ask again." — twice in one session | DONE mid-cycle at operator request (a2a4138, principle C) |
| The agreement moves mid-session | session pushed a feature branch AFTER the trunk-based rule landed; separately, another session caught the mtime change and re-read — the behaviors diverged | Step 1 makes the agreement ambient in CLAUDE.md; no extra prose |
| Passive-voice waypoints don't fire | plan-mode read as description until imperative (759e0fe); spec-review had no HOW until 768544d | Step 1 rewrite checklist: every line imperative, addressed to the session, executable as written |
| Diff-vs-stat approval regression | only observed under >400k context bloat; not recurred in fresh sessions | DROP as prose; the boundary rule is the fix |
| No product awareness in sessions | org-team-discovery stub: "a product decision is owed" because the session cannot know if reaching more teams is wanted; VISION.md/Scope never consulted (told to ignore the legacy pile it lives in) | Step 1: product frame FIRST in new CLAUDE.md + line-of-march file sessions can read and handoffs update |

## Housekeeping (principle F)

- Specs swept, all 12 statuses valid: 4 COMPLETE, 1 PARKED (identifier-validity,
  funded), 1 OPEN (season-year filter — decision owed), 6 STUB.
- Sessions older than this audit: all working sessions closed or idle-finished;
  the 500k rung-c session (ab53760d) is done and must not take new questions.
- Repo: tree clean, no worktrees, no orphan branches; 2 commits unpushed at
  audit time (b8db263, a2a4138). Kept branches (E-228, codex draft) unchanged.

## Operator decisions owed (queued for one sitting, after Step 1)

1. org-team-discovery-and-roster-ingest — does the product WANT bulk team
   discovery via organizations? (vision-adjacent; consider with curate-the-vision)
2. rung-c-season-year-filter (OPEN) — cost/semantics call, evidence in the spec
3. docs/api redacted-prefix corpus — relax the api-docs rule vs scrub ~140 sites
   (rides task #21; recommendation on file: relax, prefixes are team-scoped IDs)

## Standing residuals (carried, not prose)

- Devcontainer pip will break like CI when its image floats to pip 26.2
- Guard latent bug: CLAUDE_HOME arm not slash-normalized — 2-line fix, fold
  into the next src-touching chunk
- codex-review skill vs first-party `codex review` comparison — owed at Step 2
- Residual one-sided game (both identifiers on empty side) — live probe, task #24

## Next in line

Step 1 (CLAUDE.md rewrite + line-of-march file) is priority 1 — it closes the
framing-layer defect class this audit's failures share. Then the decision
sitting, then seed §2/§3/§4.
