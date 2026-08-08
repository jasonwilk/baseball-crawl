# Migration Audit 3 — chunks 7–9: the migration steps themselves

Date: 2026-08-08. Covers Steps 1–3 of the migration (landed 2026-08-06 → 2026-08-08).
Prior: audits 1 (`f8bb793`) and 2 (`d6645de`). Cadence: per 3 landed chunks.

## Scorecard

| chunk | commits | escaped defects | notes |
|---|---|---|---|
| 7. Step 1 — CLAUDE.md rewrite + line of march | 73e3d5e, a4df45b | 0 functional (one stale figure in a commit msg, left as cosmetic) | 1 boundary miss: answered "what would the cap need to be?" by RAISING it. ~65 min active |
| 8. Step 2 — retire the choreography | 3ed23c5, 78e5f17 (142 files, −2618) | 0 | Phase order proven against a pristine tree; positive-control gate run all four legs; ~60 min active; ceiling 458k (boundary rule strained, held) |
| 9. Step 3 — specs live | b03d9c0, 504b5a8 (295 files) | 0 | Best-executed chunk. Two-approval flow validated first try after the plan-mode deadlock fix; principle I fired on its own author within the hour and HELD; zero review-gate stalls; stack pushed |

Nine chunks into the new system: **zero escaped functional defects.** Ambient
context: 88KB → 13.6KB; session floors ~70k → 39.6k (−43%). The old system is
fully dismantled: 2 agents, 4 skills, 22 path-scoped rules, epics and ideas
frozen, specs surface live with template + done/ + IDEAS.md.

## The audit's headline

The defect class moved again. Audit 2 said "framing, not execution." This
cycle's failures were **workflow-vs-harness mismatches**: the card commanded
things the platform cannot do (review a spec that plan mode cannot write; a
gate demanding the impossible), and sessions "failing" were actually the card
being wrong. Both were fixed by matching the card to the harness's real
mechanics (fcb5aee: ExitPlanMode approves WRITING THE SPEC only). The test of a
waypoint is no longer "is it wise" but "is it EXECUTABLE as written by this
harness" — that is the standing lesson of this audit.

## Lesson routing (hook/test > agreement line > memory > drop)

| lesson | route |
|---|---|
| Exit codes are not presence tests (`git ls-files` exits 0 on no match; operator-caught) | tool-discipline.md line — ADDED this audit |
| Plan-mode/spec-review deadlock | RESOLVED — fcb5aee two-approval flow, validated end-to-end at Step 3 |
| Caps: tripwire not wall; never self-raise, never cut bone | RESOLVED — principle I, field-tested on its author same-session |
| Passive-voice waypoints don't fire | RESOLVED — imperative rewrite validated (step-3 session entered plan mode unprompted) |
| Step-5 reviews operator-typed → stalls | Mitigated (zero stalls at Step 3); automation experiment scheduled in the season-filter chunk (`claude -p` test + codex bake-off) |
| Rewrite a mechanism → sweep its INVOCATION sites, not just the definition (CLAUDE.md step 2 left pointing at the old route; /code-review caught it) | MEMORY (banked by the session); once-bitten — promote if it recurs |
| A receipt printed after the payload is not a receipt; second-granular temp names fabricate receipts | Fixed mechanically in codex-spec-review.sh where they occurred; no prose |
| `pii_scanner.py --staged` rename-blind (ACM vs hook's ACMR; 267 renames invisible on the Step 3 commit) | CHUNK — scheduled with its own spec; the RECURRENCE of the ACMR class (first fixed 2026-07-28) is noted as a finding: one-token fixes to enumeration filters do not propagate to sibling enumerations |
| Mutation probes vs concurrent writers; ambient listings lie (disk is truth) | Already in memory — routed, no prose |
| The archive-refs gate was already inert (4 dead pointers predate retirement, uncaught) | DROP — recorded here as evidence the retirement was correct |

## Housekeeping (principle F)

- Specs: swept by the Step 3 chunk itself — 6 COMPLETE in done/, live dir
  carries only PARKED/OPEN/STUB entries with valid statuses; IDEAS.md standing.
- Sessions: step-3 spec and execution sessions are at handoff/finished;
  everything older is closed. No worktrees, no orphan branches, tree clean,
  stack PUSHED (first time this migration).
- Jot list: cleared into this audit; audit-4 list starts empty except carried
  residuals (devcontainer pip; guard slash fix and extensionless scannability —
  both riding the next src-touching chunk; residual one-sided game probe).

## Next (mirrors .project/specs/README.md, the authoritative copy)

1. Season-year filter chunk (spec's two known P1s fixed at its step 1–2; carries
   the guard slash fix, extensionless scannability, and the review-automation
   experiment).
2. PII scanner hardening (own spec: --staged ACMR + RED test).
3. Docs sweep (retired-workflow prose + 4 dead pointers).
4. Seed §2/§3/§4, org-reachability measurement, residual-game probe.
5. Step 4 rule-trim once ~3 more chunks supply evidence; back-into-shape pass
   when the train settles.
