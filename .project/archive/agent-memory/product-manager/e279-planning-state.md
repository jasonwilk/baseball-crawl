# E-279 — RETIRED 2026-08-01 at closure. Three live items kept; everything else archived.

⚰ **This was the planning-END state file (READY 2026-07-28). E-279 is COMPLETED and archived; canonical record is `.project/archive/E-279-closure-machinery/epic.md`, and the durable summary is the E-279 entry in [archived-epics.md](archived-epics.md).** Retired rather than repointed: a planning-state file exists to hold what the epic file does not yet say, and at closure the epic file says it. **The planning detail dropped here — the 01→02/01→03 edge rationale, the hash-versus-subject citation lesson, the three-PM-generation handoff notes — is in the archived epic file and in the codification entries; none of it was unique to this file.**

## The three things that were unique here and are still LIVE

- ⚠️ **E-271's epic file is UNEDITED under a re-confirmed declination, and E-271 is still READY.** Only `E-271-03-disjoint-file-cluster.md` plus an E-271 History entry were ever authorized (E-279 OQ-2). The eight-item residual list lives in the archived E-279's TN-8c and is reachable from E-271's History, which cites it **by story ID rather than path** so it survives archiving. **Do NOT "finish the job" on E-271 without a fresh operator authorization.**
- ⚠️ **The `ACM`→`ACMR` PII-gate fix is a separate, already-landed commit and must NOT be "restored."** Subject *"fix: PII pre-commit gate enumerates renamed files (ACM -> ACMR)"*, 2026-07-28 — operator-ruled standalone so a security change would not reach the operator inside a closure-machinery diff. **An implementer editing `.githooks/pre-commit` will find `ACMR` at approximately `:24` and should leave it.** Neither `ACM` nor `ACMR` contains `D`.
- **IDEA-232** (`.githooks/pre-commit` `:8-11` skips the doc-PII gate) — CANDIDATE, owner claude-architect. **Promote when someone is already editing that file.** `.project/ideas/README.md` is canonical.

## Why this file is a tombstone rather than a deletion

**Retiring is not deleting, and the difference is the three items above** — each is a constraint on work that has not happened yet, and each would have been lost by a clean `rm`. **The rest was duplicated or superseded, which is what made retirement the right disposition rather than preservation.** Recorded per `.claude/rules/context-layer-assessment.md` Deletion-Side Eviction: *"a hit is a candidate for eviction, not an automatic strike; preserve still-valid guidance."*
