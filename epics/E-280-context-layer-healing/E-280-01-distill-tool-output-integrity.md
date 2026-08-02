# E-280-01: Distill tool-output-integrity.md — every rule survives, narratives become pointers

## Epic
[E-280: Context-Layer Healing](./epic.md)

## Status
`TODO`

## Description
After this story, `.claude/rules/tool-output-integrity.md` is materially smaller in bytes while stating every rule it stated before. The nine epic incident narratives it currently carries move to a casebook file under `.project/research/`, reachable from the rule file by pointer. The rule file is the single largest component of every agent's always-on context load, so this is the epic's largest single win.

## Context
The file is 29,251 bytes — **32% of the ~92 KB / ~23,000-token always-on load** every agent pays every session (TN-9). It is 98 lines, 4,850 words, with 21 paragraphs over 600 characters. Most of that mass is incident narrative: E-276 ×7, E-278 ×4, E-277 ×4, E-270 ×4, plus E-272, E-267, E-256, E-231, E-230. The narratives earn their place — this repo's record is that a rule without its incident gets re-litigated — but they do not need to be resident in every context window to do that job.

Two hazards specific to this file, both from the repo's own record:

**The author will not catch their own defect here.** `.claude/rules/tool-output-integrity.md` itself records the detection statistic: in 8 of 8 cases, the author never caught their own. That is why the enumeration in AC-1 is pre-registered against the pre-change text rather than reconstructed afterwards from the diff.

**Ambient copies of this file have been observed stale against disk.** On 2026-08-01 an agent found that at least two paragraphs present on disk did not appear in the copy injected into its context. The paragraphs are deliberately not named here — naming them would let an implementer satisfy the check without reading disk. Enumerate against the file as read from disk in your own session.

## Acceptance Criteria
- [ ] **AC-1**: An enumeration worklist artifact exists with one row per rule in the pre-change file, where a "rule" is any numbered rule or bolded rule-sentence. Every row quotes its pre-change literal text. **RED**: a row whose quoted text does not appear verbatim in the pre-change blob, or a rule present in the pre-change blob with no row.
- [ ] **AC-2**: The enumeration records the pre-change file's line count and byte size as read from disk, and those two figures match an independent measurement taken at review time. **RED**: either figure disagrees with the reviewer's own measurement.
- [ ] **AC-3**: Every row carries a written verdict naming where that rule lives after the change — including the verdict `carried unchanged`. **RED**: any row with no verdict, or a verdict naming a location that does not contain the rule.
- [ ] **AC-4**: No rule is dropped. **RED**: any row whose verdict is a removal, or whose named successor location does not contain the rule when read.
- [ ] **AC-5**: The rule file is strictly smaller in bytes after the change, and both figures are recorded. **RED**: after ≥ before. (**Bytes are this story's primary measure**, and they are measured directly — `wc -c` on the file — not inferred from any subtree tool. Per epic TN-4(b), a line count is the wrong instrument for long-paragraph prose: this file runs ~300 bytes per line, so halving its bytes moves few lines.)
- [ ] **AC-5a**: The **always-on load** is measured before and after, and both figures recorded. The pre-change reading is **92,419 bytes ≈ 23,000 tokens** (`CLAUDE.md` plus the seven `paths: "**"` rules; this file is 29,251 B of it, 32%). **RED**: after ≥ before, or either figure absent. The design owner's one-command measurement, offered as a starting point rather than a required invocation:
      ```
      tot=0; for f in .claude/rules/*.md; do head -8 "$f" | grep -q '"\*\*"' && tot=$((tot+$(wc -c <"$f"))); done; echo $((tot+$(wc -c <CLAUDE.md)))
      ```
      (This replaces the charter's original "ratchet-verified net drop", which no longer exists as a gate. It prices the quantity the epic actually cares about — what every agent pays every session — and epic TN-9 carries the derivation. **Treat 92,419 as EVIDENCE of the pre-state, not as a criterion to hit:** if your own measurement disagrees, report the divergence rather than reconciling to this number.)
- [ ] **AC-6**: The `.claude/rules` subtree line count is strictly lower after the change than before it, both figures recorded. **RED**: not lower. (A **secondary diagnostic**, measured with `.claude/hooks/context-ratchet.sh`, which is an on-demand diagnostic and no longer a gate — the operator retired the gate on 2026-08-02, epic OQ-1. This AC asserts a property of this story's own edit; it is not a baseline check, nothing is offset against it, and no exception is available or needed. Its RED is real and reachable: a distillation that only reflowed paragraphs would fail it.)
- [ ] **AC-7**: The moved narratives land under `.project/research/` and **not** under `.claude/agent-memory/`. **RED**: any file under `.claude/agent-memory/` gains the moved narrative text. (Rationale, restated without the retired instrument it was first argued from: agent-memory is *inside* the context layer, so moving narrative there relocates it rather than removing it — resident for all agents becomes deferred for one, which is a smaller win than it looks and leaves the mass in the layer. `.project/research/` is outside the layer entirely. This argument stands on its own and never depended on ratchet credit.)
- [ ] **AC-8**: Every narrative that moved is reachable from the rule file by a pointer naming both the casebook file and the specific incident. **RED**: a narrative in the casebook with no inbound pointer, or a pointer whose named target heading does not exist.
- [ ] **AC-9**: The criterion-versus-evidence cut is applied per TN-5 — a figure a reader must *meet* may be restated; a figure a reader must *see as observed* is preserved verbatim. Each figure the change touches carries a written classification. **RED**: a touched figure with no classification, or an evidence figure whose value was altered.

## Technical Approach
Read the file from disk before doing anything else; do not work from an ambient or injected copy. Produce the AC-1 enumeration and report it before making the first edit to the rule file — the pre-registration is what makes AC-3 and AC-4 checkable rather than retrospective.

The distillation target is narrative mass, not rule count. A rule's incident becomes a pointer of the form "see [casebook], [incident]" where the incident retains whatever evidence figures the rule depends on. Where a rule's force comes from a specific quoted sentence or a measured figure, that text stays in the rule file — the pointer is for the story around it.

`.claude/rules/doc-sweep.md` governs the sweep discipline and is directly relevant: a quoted tombstone is grep-indistinguishable from a live claim, and the count can move in the wrong direction after a successful sweep. Resolve each hit by reading it, never by counting.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

⚰ **RETIRED 2026-08-02, do not reinstate:** ~~Blocks: E-280-02 (which amends this file's two-cause differential once the freeze-tree mechanism exists)~~. That edge is residue from the epic's first decomposition. The restructured E-280-02 says in as many words *"Do not touch `.claude/rules/tool-output-integrity.md`"* and lists exactly one file, which is not this one. **This story and E-280-02 share no file and pass no artifact; they are independent.** The freeze arguably obviates the dispatch half of the two-cause differential, but retiring a rule because a mechanism obviates it is a different change from compressing narrative, and mixing the two would make this story's "every rule survives" unfalsifiable.

## Files to Create or Modify
- `.claude/rules/tool-output-integrity.md` (modify — distill)
- `.project/research/2026-08-01-tool-output-integrity-casebook.md` (create — the moved narratives)
- The AC-1 enumeration worklist (implementer's choice of location under `.project/research/`; it is a deliverable, not a scratch file)

## Agent Hint
claude-architect

## Handoff Context
None. (⚰ **RETIRED 2026-08-02:** ~~Produces for E-280-02: the distilled two-cause differential section, which E-280-02 amends to record that the freeze tree makes the dispatch half unreachable~~ — E-280-02 does not touch this file. See Dependencies.)

The two-cause differential section survives the distillation like every other rule, under AC-3 and AC-4. Nothing downstream in this epic reads it.

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] The enumeration worklist is committed as an artifact, not summarized in a message
- [ ] `.claude/rules/doc-sweep.md` three-step discipline applied to the moved concepts
- [ ] No regressions in existing tests

## Notes
Nine narratives is the count CA measured; treat it as the floor for the enumeration, not the target. If reading the file surfaces a tenth, it is in scope.
