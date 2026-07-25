# E-272-04: NRBL section + season-axis model in pitch-rules.md

## Epic
[E-272: Season × Level → League Classification (+ NRBL)](epic.md)

## Status
`DONE`

## Description
After this story is complete, `.claude/rules/pitch-rules.md` documents NRBL as an implemented pitch-count league, expresses the season as a classification axis in its League-to-Classification mapping, reconciles its "Forward direction (E-263)" note so the E-263 (operator-pick) and E-272 (season-axis inference) directions read coherently, and its frontmatter `paths:` glob covers every file that reads the season signal for league selection.

## Context
`pitch-rules.md` is the cross-league reference that points at the two rule-value homes (the engine constants and the baseball-coach model doc) without duplicating them. E-272 makes three changes it must reflect: NRBL exists as an implemented league, season is now a classification axis, and the E-263 "Forward direction" note needs the SELECTION-vs-MAPPING reconciliation (Technical Notes TN-6) so it doesn't assert two conflicting "how the level is chosen" stories. This is a context-layer file owned by claude-architect. It depends on E-272-03 (references the coach doc's NRBL curve) and logically follows E-272-02 (documents shipped behavior and needs its confirmed season-reading file list for the frontmatter). Per the standing practice on context-layer epics, claude-architect designed this story's shape; the ACs below frame the required outcomes.

## Acceptance Criteria
- [ ] **AC-1 (NRBL section)**: `.claude/rules/pitch-rules.md` gains an NRBL section in the same shape as the Legion section — Applicability (summer NRBL), a Status line reading "Implemented in engine" (selected via `get_rules_for_league('nrbl')`, distinct `NRBL` constant), the rest table REFERENCING the baseball-coach model doc rather than inlining the numbers (mirroring how the Sub-Varsity section points at the model doc), and a distinct-constant rationale sentence modeled on the existing `PITCH_SMART_15_18` note. The League-to-Classification Mapping table gains an NRBL row, marked as **inference-resolved** (empty-`ngb` path; NO `program_type`/`classification` DB value — filling those columns would fabricate a program_type NRBL does not have), NOT DB-field-keyed (CA-F1).
- [ ] **AC-2 (season as a classification axis)**: The League-to-Classification Mapping table expresses the season dimension (a Season column valued "any" for the season-invariant rows — the mapped-bracket and Legion-keyword rows — and spring/summer on the NSAA level-word rows, which ALL flip by season per TN-2 §4c), plus a short "Season as a classification axis" subsection stating the precedence ladder from Technical Notes TN-2 (mapped age brackets dispositive over ALL name keywords; recognized ngb wins over bracket; level words season-disambiguated per §4c; no-season default = spring/NSAA). The NRBL and season-flip rows are marked inference-resolved (empty-`ngb` path, no DB fields), NOT DB-field-keyed (CA-F1). The "(league × competition level × season-phase)" keying phrase this model refines lives in the baseball-coach model doc (E-272-03), NOT in pitch-rules.md — attribute it there; do not claim it as pitch-rules.md's existing text (CA-F2).
- [ ] **AC-3 (E-263 reconciliation)**: The existing "Forward direction (E-263)" note is reworded per Technical Notes TN-6's SELECTION-vs-MAPPING split — E-263 changes how the LEVEL is chosen (name-keyword guess → operator pick); E-272 adds SEASON as an authoritative MAPPING axis that survives the E-263 transition; the unset fallback delegates to `detect_league_level` inference. The doc does not assert two conflicting "how the level is chosen" stories, and the doc-sweep discipline (`.claude/rules/doc-sweep.md`) is applied so no stale "inference is only the gap / operator-pick is the sole fix" phrasing survives elsewhere in the file.
- [ ] **AC-4 (frontmatter coverage)**: The `pitch-rules.md` frontmatter `paths:` glob covers every file that reads the season signal for league selection — at minimum `src/reports/generator.py` (the confirmed season-threading call site, not currently globbed), plus any additional season-reading site E-272-02 reports. A future edit to that site auto-loads this rule.
- [ ] **AC-5 (provenance tags — inline, matching convention)**: E-272's additions are marked with inline epic tags matching the doc's ACTUAL provenance convention (the "(E-243-02)" / "Forward direction (E-263)" inline-tag style) — pitch-rules.md has NO "Last-updated / Source" header (only 2 of 34 rule files carry one; it is not a project convention) and none is added (CA-F3).
- [ ] **AC-6 (stale agent-def line — folded from E-272-03 per Codex-P2-a + coach's file-owner ruling)**: The stale line at `.claude/agents/baseball-coach.md:33` — verified to literally read "**Roster carryover is ~80%.** LSB Reserve maps to sophomore-level Legion." — is corrected so LSB Reserve maps to **NRBL** (the sophomore-age, reserve-tier summer league) instead of "sophomore-level Legion", since E-272 establishes NRBL as the summer reserve-tier league. This is a claude-architect-owned agent-def file already in this story's context-layer scope; the `~80%` roster-carryover fact and the surrounding sentence are preserved.
- [ ] **AC-7 (primary-source cites + season-phase scoping)**: Each of the NSAA, Legion, and NRBL sections carries a one-line `*Source:*` cite per Technical Notes TN-10 (NSAA → the 2022 Pitch Count Regulations PDF URL; Legion → ALB Senior/Junior regulations; NRBL → follows ALB, `nrbl.net`), and the "Season as a classification axis" subsection (AC-2) ENDS with a single disambiguation sentence scoping the pre/post-April-1 date PHASE to NSAA Varsity ONLY (Sub-Varsity + all summer leagues flat year-round; Junior≡Senior≡NRBL) — explicitly distinct from the season AXIS so a reader does not read a date threshold into the new axis. The NSAA source cite must agree with the coach model doc's provenance (E-272-03) — same source, no drift. Additions are ~4 lines (ratchet-negligible, TN-10).

## Technical Approach
Edit `.claude/rules/pitch-rules.md`: add the NRBL section (clone the Legion section shape; reference the coach model doc for numbers), add the season column + "Season as a classification axis" subsection to the mapping table, reword the "Forward direction (E-263)" note per TN-6, and add `src/reports/generator.py` (plus any additional season-reading site from E-272-02) to the frontmatter `paths:`. Apply the doc-sweep discipline (token grep + synonym expansion + semantic read) to confirm no contradictory inference-vs-operator-pick phrasing survives. Reference, do not duplicate, coach's rest-curve numbers. Separately, correct the one stale sentence at `.claude/agents/baseball-coach.md:33` (AC-6) — both files are claude-architect-owned.

## Dependencies
- **Blocked by**: E-272-03 (references the coach model doc's NRBL curve), E-272-02 (documents shipped behavior; supplies the confirmed season-reading file list for AC-4)
- **Blocks**: None

## Files to Create or Modify
- `.claude/rules/pitch-rules.md` (modify — NRBL section, season-axis mapping, E-263 reconciliation, frontmatter `paths:`, inline E-272 provenance tags)
- `.claude/agents/baseball-coach.md` (modify — line 33: correct "LSB Reserve maps to sophomore-level Legion" → NRBL, preserving the `~80%` roster-carryover sentence)

## Agent Hint
claude-architect

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Doc-sweep discipline applied (grep + synonym expansion + semantic read) — no stale/contradictory league-selection phrasing survives
- [ ] NRBL's rest-curve numbers referenced (not duplicated) from the coach model doc, mirroring the Sub-Varsity section; the existing inlined NSAA Varsity / Legion tables are unchanged and out of scope (no de-inlining refactor — Codex-P2-b)
- [ ] Frontmatter `paths:` covers every confirmed season-reading league-selection site

## Notes
The E-263 reconciliation wording (AC-3) is the load-bearing part — the SELECTION-vs-MAPPING split is what keeps E-263 (operator-pick level selection) and E-272 (season-axis league mapping) coherent in one doc. The frontmatter fix (AC-4) closes a real gap: `generator.py` is where season gets threaded into `detect_league_level` but is not currently under the rule's `paths:` glob, so the rule would not auto-load when someone later edits that site.

AC-6 (line-33 fix) is CA-owner-confirmed: the line text matches verbatim and the "→ NRBL (sophomore-age, reserve-tier summer league)" replacement is approved. Optional adjacent polish while the file is open (CA's discretion, NOT a hard requirement — these lines are incomplete, not wrong): `.claude/agents/baseball-coach.md:32` ("HS spring ends, then Legion summer starts" could read "Legion/NRBL summer starts") and `:26` (the constituency list "Legion coaches (post-HS summer)" loosely covers summer-reserve NRBL coaches). Keeping AC-6 scoped to the clearly-wrong line 33 avoids scope creep; if CA sweeps 26/32 in the same pass for coherence, that is acceptable but not required.
