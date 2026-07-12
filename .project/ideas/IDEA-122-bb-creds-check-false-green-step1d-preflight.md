# IDEA-122: `bb creds check` false-green — Step 1d preflight must parse output, not trust the exit code

## Status
`PROMOTED` (2026-07-12) — folded into E-262 (story E-262-06, Step 1d preflight & gate-ordering corrections). Landing settled by SE+CA consult: NOT a `creds.py` command change (the original "SE root fix" direction was wrong — single-profile and all-dead-multi already exit non-zero; only the MIXED multi-profile case false-greens, and the "any valid = usable" contract must hold). Fix is skill-side option (b): the Step 1d preflight calls `bb creds check --profile web` (the profile the reports smoke uses). Re-scoped out of story 03 into story 06.

## Summary
During the E-256 Step 1d closure runtime smoke (the first live-run of the new gate), `bb creds check` was observed to **exit 0 even when the credentials are dead/expired**. The Step 1d env-preflight uses that exit code to decide whether credentials are usable before running the live reports flow — so a false-green `check` lets the preflight proceed on dead creds and then fail deeper (or mis-attribute an env problem as an epic failure). Two candidate fixes: (a) **fix `bb creds check`** to exit non-zero when the credentials cannot authenticate (the clean root fix), or (b) **make the Step 1d preflight PARSE `bb creds check`'s output** for the liveness verdict instead of trusting its exit code (defensive, skill-side).

## Why It Matters
Step 1d is the reports flow's first live runtime gate at closure; its value depends on cleanly distinguishing an **environment** failure (creds/DB not set up → escalate to operator) from an **epic** failure (the change broke something → remediate). A `bb creds check` that returns 0 on dead creds collapses that distinction — the preflight believes creds are good, runs the flow, and the real "creds are dead" cause is buried. The gate's escalate-vs-remediate routing is only as reliable as the preflight's liveness signal.

## Rough Timing
No urgency — Step 1d already functioned in E-256's closure (the operator was present to interpret the deeper failure). Promote when either surface is next touched: the `bb creds` CLI (root fix a) or the Step 1d procedure in `implement/SKILL.md` (defensive fix b). The cleaner fix is (a) — a command's exit code should reflect its verdict.

## Dependencies & Blockers
- [ ] None hard. Independent.

## Open Questions
- Is `bb creds check`'s exit-0-on-dead-creds intentional (it "successfully checked" and reported the dead state in its output) or a genuine bug? If intentional, fix (b) is correct and `check`'s contract stays; if not, fix (a).
- Does any other caller depend on `bb creds check`'s current exit-code behavior? (grep before changing the exit code.)

## Notes
Surfaced during the E-256 Step 1d closure runtime smoke live-run, 2026-07-12. **Domain: software-engineer** (`bb creds check` exit code, root fix a) OR **claude-architect** (`.claude/skills/implement/SKILL.md` Step 1d preflight, defensive fix b). Sibling finding from the same live-run: [IDEA-123].

---
Created: 2026-07-12
Last reviewed: 2026-07-12
Review by: 2026-10-10
