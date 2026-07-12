---
name: feedback-reverify-idea-before-folding
description: Before folding a backlog idea into a housekeeping/cleanup epic, re-verify its target files still exist AND still show the cited defect — old ideas get silently fixed by unrelated epics before promotion.
metadata:
  type: feedback
---

Before folding any backlog idea into a housekeeping/cleanup/fold-in epic, re-verify against the LIVE files that (a) the cited anchor files still exist and (b) they still exhibit the cited defect. Glob/grep each idea's named anchor before writing the story; if the defect is already resolved, DISCARD the idea rather than fold it.

**Why:** In E-262 planning, 2 of 4 docs-story premises were stale — the idea had been captured against a real defect, then silently fixed by an UNRELATED epic before the idea was promoted. IDEA-078 (coaching-docs dashboard framing) was fixed by E-239 *two days after* it was captured; its target `docs/coaching/scouting-reports.md` no longer even existed (renamed to `standalone-reports.md`). IDEA-092 (data-engineer.md hallucination anchors) was fixed by E-250-04. IDEA-010 (Traefik port map) was already correct in the live doc. All three were caught only because api-scout, docs-writer, and claude-architect ran holistic reviews and checked live state — not by me at fold-in time. A docs-writer dispatched against a phantom target either fails the AC or invents busywork, and under the E-260 meta-layer freeze, folding an already-fixed "defect" quietly smuggles in freeze-barred enrichment.

**How to apply:** During plan-mode fold-in (especially for old ideas — captured-date well before the epics that shipped since), for each idea: glob the cited file(s) exist, grep the cited defect token, and read the surrounding section. Idea captured-date older than an intervening epic that touched that area = high staleness risk. If the file is gone or the defect is absent, flip the idea to DISCARDED with the resolving epic cited — do NOT write a story for it. This is the fold-in analogue of [[process_epic_numbering]] (trust the filesystem, not the memory/idea record) and the [[feedback_verify_cited_facts_before_approving]] verify-before-approving discipline.
