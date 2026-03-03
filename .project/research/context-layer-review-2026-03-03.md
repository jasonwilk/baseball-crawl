# Context Layer Comprehensive Review

**Date**: 2026-03-03
**Author**: claude-architect
**Purpose**: Full audit of the baseball-crawl context layer -- CLAUDE.md, agents, rules, skills, hooks, memory, and settings. Identifies staleness, gaps, redundancy, budget drift, and proposes prioritized updates.

---

## 1. Current State Summary

### File Inventory and Sizes

| Category | File Count | Total Lines | Notes |
|----------|-----------|-------------|-------|
| **CLAUDE.md** | 1 | 297 | Root project instructions |
| **Rules** (`.claude/rules/`) | 10 | 546 | All path-scoped except workflow-discipline (`**`) |
| **Agent definitions** (`.claude/agents/`) | 7 | 1,363 | PM is the largest (327 lines) |
| **Agent MEMORY.md files** | 7 | 516 | PM (96 lines), architect (97), general-dev (86), baseball-coach (79), data-engineer (74), api-scout (72), docs-writer (12) |
| **Architect topic files** | 5 | 554 | agent-design, claude-practices, skills-and-hooks, semantic-layer, agent-blueprints |
| **PM topic files** | 2 | 92 | lessons-learned, mcp-research |
| **Skills** (`.claude/skills/`) | 3 | 464 | context-fundamentals (193), filesystem-context (199), multi-agent-patterns (72) |
| **Hooks** (`.claude/hooks/`) | 3 scripts + README | 274 | pii-check.sh, statusline.sh, epic-archive-check.sh, README.md |
| **Settings** | 2 | 39 | settings.json (31), settings.local.json (8) |

**Grand total context-layer files**: ~40 files, ~4,145 lines

### Ambient Context Budget (Per Agent Session)

What loads automatically for every agent session:

| Source | Lines | Notes |
|--------|-------|-------|
| CLAUDE.md | 297 | Up from ~232 when context-fundamentals was written |
| Rules (10 files) | 546 | Up from ~212 (6 files) when context-fundamentals was written |
| Agent definition | 139-327 | Varies; PM=327, baseball-coach=139 |
| Agent MEMORY.md | 12-97 | Varies; docs-writer=12, architect=97 |
| **Total ambient** | **~994 - ~1,267** | Depending on which agent is active |

**Budget assessment**: The context-fundamentals skill documents the ambient baseline as "~600-700 lines." The actual baseline is now **~1,000-1,270 lines** -- nearly double the documented figure. This is the most significant accuracy drift in the context layer.

The increase comes from:
- CLAUDE.md grew from ~232 to 297 lines (+65)
- Rules grew from 6 files / ~212 lines to 10 files / 546 lines (+334): new files include dispatch-pattern.md (108), documentation.md (64), ideas-workflow.md (83), devcontainer.md (131)
- Agent definitions and memory files were fleshed out as part of E-013/E-020

---

## 2. Staleness Audit

### Critical Staleness (Actively Misleading)

**S1. PM Memory: E-001 listed as ACTIVE but is actually COMPLETED and archived.**
- File: `.claude/agent-memory/product-manager/MEMORY.md` line 17
- E-001 was completed on 2026-03-03 and moved to `.project/archive/E-001-gamechanger-api-foundation/`
- PM memory still shows: `E-001 (ACTIVE): GameChanger API Foundation -- E-001-01 DONE, E-001-03 DONE, E-001-02 TODO, E-001-04 TODO`
- **Impact**: PM will try to dispatch stories for a completed epic. High risk of confusion.

**S2. PM Memory: E-034 listed as READY in Active Epics but is actually COMPLETED and archived.**
- E-034 is in `.project/archive/E-034-codex-review/` with status COMPLETED
- PM memory correctly lists it under Archived Epics (line 51) but does NOT list it under Active Epics -- actually, on re-reading, E-034 does NOT appear under Active Epics. The Archived Epics section correctly has it. However, the archived epics list is missing E-034 from the "archived" parenthetical on line 5: `E-006, E-007, E-008, E-010, E-011, E-012, E-013, E-014, E-015, E-016, E-017, E-018, E-019, E-020, E-021, E-022, E-024, E-025, E-026, E-027, E-029, E-030, E-031, E-032, E-033 archived` -- E-001, E-028, and E-034 are missing from this list.
- **Impact**: Numbering state lists "E-001 through E-034" as created but the archived parenthetical is incomplete.

**S3. Claude-architect Memory: Stale deployment details.**
- File: `.claude/agent-memory/claude-architect/MEMORY.md` line 39
- Says: "Hetzner CX11 VPS" and "Litestream"
- Reality: Home Linux server (no VPS), no Litestream (simple file backup via `scripts/backup_db.py`)
- PM memory correctly says "Home Linux server (no VPS, no hosting cost)" and "Simple file backup via scripts/backup_db.py (no Litestream)"
- CLAUDE.md correctly says "home Linux server"
- **Impact**: Architect memory directly contradicts CLAUDE.md and PM memory on a key architectural decision.

**S4. Context-fundamentals skill: Budget numbers are stale.**
- File: `.claude/skills/context-fundamentals/SKILL.md` lines 74-84, 150-171
- Documents ambient baseline as "~600-700 lines" with breakdown: CLAUDE.md ~232, rules ~212 (6 files)
- Actual: CLAUDE.md 297, rules 546 (10 files) = baseline significantly higher
- The worked example (lines 150-171) shows a "Ambient subtotal: ~654 lines" which should be ~1,000+
- **Impact**: Agents relying on this skill for context budget decisions are working with numbers that underestimate ambient load by ~50%.

**S5. pii-check.sh: Stale comment about scanner not being installed.**
- File: `.claude/hooks/pii-check.sh` line 27
- Comment says: `# Scanner not yet installed (E-019-03 pending); allow commit`
- Reality: `src/safety/pii_scanner.py` exists and has been deployed since E-019 completed
- **Impact**: Misleading comment only; the code path is the fallback for "file not found" and works correctly. But the comment is wrong -- E-019 is long completed.

**S6. Claude-architect agent definition: Says "six agents" but there are seven.**
- File: `.claude/agents/claude-architect.md` line 23
- Says: "This project has six agents working together" and only lists six (omits docs-writer)
- Reality: docs-writer was added in E-028; agent ecosystem is now seven agents
- **Impact**: Architect's own definition is wrong about ecosystem size.

### Moderate Staleness (Dated but Not Actively Harmful)

**S7. Filesystem-context skill: References `epics/E-010-intent-context-layer-implementation/epic.md`.**
- File: `.claude/skills/filesystem-context/SKILL.md` line 196
- E-010 is abandoned and archived at `/.project/archive/E-010-intent-context-layer-implementation/`
- The reference is in the "Source Material" section and is informational, not actionable
- **Impact**: Low. An agent trying to load this path would get a file-not-found error.

**S8. Agent-blueprints topic file: References "E-007" for agent creation.**
- File: `.claude/agent-memory/claude-architect/agent-blueprints.md` line 3
- Says agents were created via E-007 then E-013. E-007 was `orchestrator-workflow-discipline`, not agent creation.
- The actual creation path was E-007 created stubs, E-013 completed buildout
- **Impact**: Low. Historical reference only.

**S9. Claude-architect memory: E-030 says "Agent ecosystem now 6 agents" but docs-writer added later.**
- After E-030 removed the orchestrator, the ecosystem was 6. Then E-028 added docs-writer making it 7.
- The archived E-030 note is historical and correct for its time but the architect memory does not note the subsequent addition.
- **Impact**: Low. The "Agent Ecosystem (Current)" section at the top of architect MEMORY.md also only lists 6 agents.

**S10. PM memory: E-005 listed as ACTIVE with E-005-03 blocked on E-001-02.**
- E-001 is now COMPLETED, so E-001-02 must be DONE. E-005-03's blocker may have cleared.
- PM memory has not been updated to reflect this cascade.
- **Impact**: Moderate. PM might not know E-005-03 is now unblocked.

**S11. PM memory: Architecture section says `src/gamechanger/` but the actual directory is `src/`.**
- Line 12: `Architecture: src/gamechanger/ for source, src/api/ for FastAPI app`
- Actual structure: `src/` contains `api/`, `gamechanger/`, `http/`, `safety/`, `__init__.py`
- **Impact**: Low. The reference is partially correct but imprecise.

---

## 3. Gap Analysis

### Documented but Not Practiced

**G1. Dispatch-pattern agent selection table does not include docs-writer.**
- The table maps story domains to agent types but has no row for documentation stories.
- docs-writer is mentioned in the Closure Sequence (step 11) but not in the Agent Selection table.
- When a doc story is dispatched, the PM has no routing guidance in the table.
- **Recommendation**: Add a row: `Documentation (docs/admin/, docs/coaching/) | docs-writer`

**G2. Direct-routing exceptions list does not include docs-writer.**
- CLAUDE.md, workflow-discipline.md, and dispatch-pattern.md list api-scout, baseball-coach, and claude-architect as direct-routing exceptions.
- docs-writer requires PM intermediation (by design), which is correct.
- But docs-writer is also not listed in the "Implementing agents" column of the PM consultation triggers table.
- **Recommendation**: Verify docs-writer's routing is clear. It is an implementing agent (requires story reference) dispatched by PM. The dispatch-pattern table should include it.

**G3. No rule or convention for `scripts/` directory.**
- Seven scripts exist: `backup_db.py`, `codex-review.sh`, `codex-spec-review.sh`, `install-hooks.sh`, `refresh_credentials.py`, `reset_dev_db.py`, `seed_dev.py`, `smoke_test.py`.
- CLAUDE.md's Commands section only lists three (install-hooks.sh, codex-review.sh, codex-spec-review.sh).
- No rule file scoped to `scripts/**` to guide how scripts should be written.
- **Recommendation**: Low priority. The three documented commands are sufficient for now. Consider adding the remaining scripts to Commands if they are regularly used by agents.

### Practiced but Not Documented

**G4. `data/raw/` directory mentioned in PM memory but not in CLAUDE.md Architecture section.**
- PM memory line 12 mentions `data/raw/ for crawl output`
- CLAUDE.md Architecture section says `data/` for local dev outputs but does not call out `data/raw/`
- **Recommendation**: Low priority. Update when E-002 delivers the crawl pipeline.

**G5. No documentation of the `apply_migrations.py` runner in CLAUDE.md.**
- The data-engineer agent definition and data-engineer memory both reference it.
- CLAUDE.md mentions migrations directory but not the runner.
- General-dev may need to know about the runner when writing loaders that depend on schema.
- **Recommendation**: Low priority. Agent definitions carry the context. Could add to CLAUDE.md Architecture section when migration work becomes active.

**G6. Codex review scripts are new and not yet integrated into agent workflow.**
- E-034 delivered the scripts and updated CLAUDE.md Commands and PM agent def.
- But no agent other than PM knows about spec-review. No rule triggers codex review.
- **Recommendation**: This is by design -- E-034's PM workflow integration makes it optional. No action needed.

---

## 4. Redundancy Check

### High Redundancy (Same Content in Multiple Places)

**R1. Ideas workflow documented in 4 places.**
- Already noted in architect MEMORY.md (line 46-50) as a known pattern.
- Content is in: CLAUDE.md (Ideas vs Epics, ~16 lines), rules/ideas-workflow.md (83 lines, full detail), rules/project-management.md (25 lines, summary), product-manager.md (15 lines, PM-specific workflow).
- All four are consistent with each other.
- **Assessment**: Acceptable redundancy. CLAUDE.md has the summary, the rule has the full detail, PM has the PM-specific perspective. They serve different audiences (ambient vs. scoped vs. agent-specific).

**R2. Epic/story workflow documented in 3+ places.**
- CLAUDE.md (Project Management section, ~48 lines), rules/project-management.md (50 lines), rules/workflow-discipline.md (42 lines), product-manager.md (Dispatch Mode ~80 lines, System of Work ~30 lines), rules/dispatch-pattern.md (108 lines).
- The dispatch-pattern.md and product-manager.md carry the detailed dispatch procedure; CLAUDE.md and workflow-discipline carry the summary.
- **Assessment**: The split is intentional -- CLAUDE.md is the summary, dispatch-pattern.md is the operational detail, PM agent def is the PM-specific procedure. However, workflow-discipline.md and project-management.md overlap significantly. workflow-discipline repeats the READY gate, work authorization gate, PM task types, and direct-routing exceptions -- all of which are already in CLAUDE.md.

**R3. HTTP Request Discipline documented in CLAUDE.md and general-dev MEMORY.md.**
- CLAUDE.md has the full HTTP Request Discipline section (~28 lines).
- general-dev MEMORY.md reproduces much of it (~24 lines under "HTTP Request Discipline").
- api-scout MEMORY.md has a condensed version (~8 lines under "HTTP Request Discipline").
- **Assessment**: The memory files should reference CLAUDE.md rather than duplicate. This violates the architect anti-pattern "never duplicate CLAUDE.md content in agent system prompts" -- the MEMORY.md files are ambient context just like system prompts.

**R4. Security rules documented in CLAUDE.md, api-scout.md, api-scout MEMORY.md.**
- CLAUDE.md Security Rules (5 lines), api-scout.md Security Rules (6 lines with detail), api-scout MEMORY.md Security Rules (7 lines).
- The api-scout versions add API-specific detail (placeholder names, auth header stripping).
- **Assessment**: Marginal. The api-scout-specific additions are justified, but the base rules are duplicated.

**R5. Code style rules in CLAUDE.md, rules/python-style.md, general-dev MEMORY.md.**
- CLAUDE.md Code Style (5 lines), rules/python-style.md (17 lines, more detail), general-dev MEMORY.md Python Style (6 lines).
- The rule file adds `from __future__ import annotations`, f-strings, context managers, PEP 8 naming, function length limit.
- **Assessment**: python-style.md is the correct place for the detail. CLAUDE.md summary is fine. general-dev MEMORY.md duplicates both.

### Low Redundancy (Acceptable Cross-References)

**R6. Testing rules in CLAUDE.md, rules/testing.md, general-dev MEMORY.md.**
- CLAUDE.md Testing (3 lines), rules/testing.md (17 lines), general-dev MEMORY.md Testing Rules (12 lines).
- Same pattern as R5. The memory file duplicates the rule.

**R7. Database conventions in data-engineer.md, data-engineer MEMORY.md, baseball-coach MEMORY.md, general-dev MEMORY.md.**
- Each carries the conventions relevant to its role. Some overlap (ip_outs, splits, soft referential integrity) appears in all four.
- **Assessment**: This is borderline. Each agent needs these conventions in its working context. Extracting to CLAUDE.md would add ~10 lines to ambient context for all agents. Leaving in memory files means each agent has it when needed. Current approach is acceptable.

---

## 5. Structural Issues

### ST1. workflow-discipline.md scoped to `**` (all paths)
- File: `.claude/rules/workflow-discipline.md`
- Scoped with `paths: ["**"]` -- loads on every file touch, making it effectively unconditional.
- This is the same as having no path scope at all.
- The content (epic READY gate, work authorization, routing rule, PM task types, direct-routing exceptions, documentation assessment gate, dispatch failure protocol) is all project management process, not file-specific.
- **Recommendation**: Either remove the paths field entirely (making it unconditional, which is what it already is) or scope it to `epics/**` and `.project/**` where it is most relevant. Since the Work Authorization Gate and Dispatch Failure Protocol apply to all agents regardless of file path, unconditional is appropriate -- just remove the misleading `paths: ["**"]`.

### ST2. dispatch-pattern.md is both a rule file and an operational manual.
- At 108 lines with 7 major sections, it is one of the larger rules.
- It is scoped to no paths (unconditional), which is correct since it defines the overall dispatch procedure.
- However, much of its content is duplicated in product-manager.md (which reproduces the full dispatch procedure).
- **Assessment**: The duplication is intentional -- PM needs the full procedure in its agent definition, and other agents need to understand the dispatch contract from the rule. This is an acceptable pattern.

### ST3. Agent selection table in dispatch-pattern.md uses `general-purpose` agent type.
- The table says to use `general-purpose` for Python, database, and API stories.
- This is a Claude Code built-in agent type (not one of our custom agents).
- The table notes "(data-engineer role in prompt)" and "(api-scout role in prompt)" for specialized uses.
- **Assessment**: This works because when PM spawns a `general-purpose` teammate, it includes the full story file and context, which gives the agent enough direction. However, it means data-engineer and api-scout agent definitions are never used during dispatch -- they exist only for direct routing. This is a design decision that could be revisited if implementing agents need their full agent persona during dispatch.

### ST4. docs-writer has no row in the dispatch-pattern agent selection table.
- See G1 above. The table does not guide PM on how to dispatch documentation stories.
- The PM agent definition mentions docs-writer dispatch in the closure sequence but not in the main dispatch procedure.

---

## 6. Budget Assessment

### Context-Fundamentals Accuracy

The context-fundamentals skill (`.claude/skills/context-fundamentals/SKILL.md`) documents the ambient context budget with specific numbers. Here is the comparison:

| Item | Documented | Actual | Delta |
|------|-----------|--------|-------|
| CLAUDE.md | ~232 lines | 297 lines | +65 (+28%) |
| Rules (file count) | 6 files | 10 files | +4 files |
| Rules (total lines) | ~212 lines | 546 lines | +334 (+158%) |
| Agent definition (range) | ~100-200 lines | 139-327 lines | +27 to +127 |
| Agent MEMORY.md (range) | Variable | 12-97 lines | Undocumented |
| **Ambient subtotal** | **~600-700 lines** | **~994-1,267 lines** | **+44% to +81%** |

The worked example in the skill shows a typical story session reaching ~1,204 lines total (ambient + task). With the corrected ambient baseline, a similar session would reach ~1,550-1,600 lines -- still well within a 128k context window, but the percentage estimate would shift from "~20-25%" to "~25-30%".

The practical impact is moderate: the threshold guidance (green/yellow/red zones) is based on percentage, not absolute line counts, so it remains valid. But the worked example and budget breakdown are materially incorrect and could mislead an agent doing precise context management.

### Rules Growth Trajectory

The rules directory has grown from 6 to 10 files, more than doubling in line count. The new rules (dispatch-pattern, documentation, ideas-workflow, devcontainer) are all justified by real needs. However, the total ambient load from rules (546 lines) now exceeds CLAUDE.md itself (297 lines). This is not a problem per se, but it means that rules -- which are all unconditionally loaded -- are the single largest contributor to ambient context.

Two rules are notably large relative to their peers:
- `devcontainer.md`: 131 lines (scoped to `.devcontainer/**`, Dockerfile, docker-compose*)
- `dispatch-pattern.md`: 108 lines (unconditional, also loaded into PM agent prompt as system instructions)

The devcontainer rule is well-scoped and only loads when devcontainer/Docker files are touched. The dispatch-pattern rule loads unconditionally, adding 108 lines to every session.

---

## 7. Cross-Reference Integrity

### Verified Cross-References (Correct)

- CLAUDE.md Agent Ecosystem table matches actual `.claude/agents/` directory (7 agents)
- CLAUDE.md Workflow Contract references `dispatch-pattern.md` correctly
- CLAUDE.md Direct-Routing Exceptions match workflow-discipline.md
- Settings.json hooks reference existing scripts with correct paths
- Agent definitions reference existing skill files
- PM agent definition references existing template paths

### Broken or Stale Cross-References

| Reference | Location | Issue |
|-----------|----------|-------|
| `epics/E-010-intent-context-layer-implementation/epic.md` | filesystem-context SKILL.md line 196 | E-010 is archived, path is now `.project/archive/...` |
| "E-019-03 pending" | pii-check.sh line 27 | E-019 completed; scanner exists |
| "six agents" | claude-architect.md line 23 | Seven agents after E-028 added docs-writer |
| "6 agents" | architect MEMORY.md (via E-030 note) | Seven after docs-writer addition |
| "Hetzner CX11 VPS" + "Litestream" | architect MEMORY.md line 39 | Home Linux server, no Litestream |
| E-001 as ACTIVE | PM MEMORY.md line 17 | E-001 is COMPLETED and archived |
| `src/gamechanger/ for source` | PM MEMORY.md line 12 | Partially correct but imprecise |

---

## 8. Proposed Updates (Prioritized)

### Priority 1: Fix Actively Misleading Content

These should be addressed immediately as they can cause agents to make wrong decisions.

**P1.1. Update PM MEMORY.md: Remove E-001 from Active Epics.**
- E-001 is COMPLETED and archived. Remove the line from Active Epics.
- Add E-001 to the archived parenthetical on line 5 and to the Archived Epics section.
- Also add E-028 and E-034 to the archived parenthetical.
- Check if E-005-03's blocker (E-001-02) is now cleared and update E-005 entry accordingly.

**P1.2. Update architect MEMORY.md: Fix deployment details.**
- Line 39: Change "Hetzner CX11 VPS" to "Home Linux server"
- Line 39: Remove "Litestream" reference; replace with "simple file backup via scripts/backup_db.py"
- Line 19-26: Add docs-writer to the Agent Ecosystem list

**P1.3. Update context-fundamentals skill: Correct budget numbers.**
- Update the ambient budget table (lines 74-84): CLAUDE.md ~297, rules ~546 (10 files), total ~1,000-1,270
- Update the worked example (lines 150-171) with corrected numbers
- Keep the percentage-based threshold guidance (green/yellow/red) unchanged -- it remains valid

**P1.4. Update claude-architect agent definition: Fix agent count.**
- Line 23: Change "six agents" to "seven agents" and add docs-writer to the list
- Add docs-writer to the Inter-Agent Coordination section

### Priority 2: Fix Stale References and Minor Inaccuracies

**P2.1. Fix pii-check.sh comment.**
- Line 27: Change `# Scanner not yet installed (E-019-03 pending); allow commit` to something like `# Scanner not found at expected path; allow commit (fail open)`

**P2.2. Fix filesystem-context skill E-010 reference.**
- Line 196: Update the path to `/.project/archive/E-010-intent-context-layer-implementation/epic.md` or remove the reference entirely (it is informational, not actionable)

**P2.3. Update dispatch-pattern agent selection table to include docs-writer.**
- Add row: `| Documentation (docs/admin/, docs/coaching/) | docs-writer |`
- This fills gap G1 and gives PM explicit routing guidance for documentation stories

**P2.4. Clean up workflow-discipline.md paths field.**
- Remove `paths: ["**"]` since it is effectively unconditional already. Or explicitly comment that it is intentionally global.

### Priority 3: Reduce Redundancy (Low Urgency)

**P3.1. Trim general-dev MEMORY.md duplication.**
- The HTTP Request Discipline section (~24 lines) largely duplicates CLAUDE.md.
- The Python Style section (~6 lines) duplicates rules/python-style.md.
- The Testing Rules section (~12 lines) duplicates rules/testing.md.
- Replace with brief references: "See CLAUDE.md HTTP Request Discipline section" and "See .claude/rules/python-style.md"
- Keep only general-dev-specific additions (session factory location, respx/responses distinction)

**P3.2. Trim api-scout MEMORY.md HTTP Request Discipline section.**
- The section (~8 lines) duplicates CLAUDE.md. Replace with a reference plus any api-scout-specific additions.

**P3.3. Consider whether workflow-discipline.md and project-management.md overlap justifies consolidation.**
- workflow-discipline.md (42 lines) and project-management.md (50 lines) cover similar ground.
- workflow-discipline is global scope; project-management is scoped to `epics/**` and `.project/**`.
- They could potentially be merged into a single rule. However, the scoping difference means project-management only loads when touching project management files, while workflow-discipline is always loaded.
- **Decision**: Leave as-is for now. The overlap is ~15 lines and the scoping serves different purposes.

### Priority 4: Structural Improvements (Future Consideration)

**P4.1. Consider scoping dispatch-pattern.md.**
- At 108 lines loaded unconditionally, it is one of the largest ambient contributions.
- In practice, dispatch-pattern is only relevant when PM is dispatching stories.
- Moving it to a PM-only ambient file or scoping it to `epics/**` would save ~108 lines of ambient context for non-PM agents.
- **Counterargument**: All agents need to understand the dispatch contract (e.g., implementing agents need to know they should not update statuses). The current unconditional loading is defensible.
- **Recommendation**: Defer. Monitor whether the ambient load becomes a problem. Currently ~1,000-1,270 lines is manageable.

**P4.2. Consider whether architect topic files are still needed at current sizes.**
- Five topic files totaling 554 lines. Only loaded on demand.
- `agent-blueprints.md` (106 lines) contains historical blueprints that are superseded by actual agent files. Could be trimmed significantly.
- `agent-design.md` (114 lines) documents platform capabilities. Still useful as a reference.
- **Recommendation**: Trim `agent-blueprints.md` to a brief historical note since the actual agent files are the authoritative source. Otherwise, leave topic files as-is.

**P4.3. Docs-writer MEMORY.md is nearly empty.**
- Only 12 lines with placeholder sections ("To be populated as documentation work begins").
- This is fine -- the agent was recently created and has had minimal usage.
- **Recommendation**: No action. Will populate naturally as documentation work occurs.

---

## 9. Summary of Findings

### What Is Working Well

1. **Agent ecosystem structure**: Seven agents with clear responsibilities, well-defined boundaries, and explicit inter-agent coordination sections. The dispatch-pattern and workflow-discipline rules enforce the coordination model.

2. **Ambient/deferred context separation**: Skills are properly deferred with explicit activation triggers. Agent definitions reference skills conditionally. MEMORY.md files stay under 200 lines.

3. **Hook infrastructure**: Three hooks (pii-check, epic-archive-check, statusline) all function correctly. Settings.json is clean and well-organized. Hooks are deterministic checks, not reasoning tasks -- per design principles.

4. **Rules scoping**: Most rules are appropriately scoped. python-style.md scopes to `**/*.py`, testing.md to `tests/**`, crawling.md to crawler/fetcher patterns, devcontainer.md to devcontainer/Docker files, documentation.md to `docs/**` and `epics/**`.

5. **Memory organization**: PM and architect have topic files for detailed notes, keeping MEMORY.md concise. Other agents have streamlined MEMORY.md files appropriate to their usage level.

### What Needs Attention

1. **PM MEMORY.md active epics list is stale.** E-001 is completed but still listed as ACTIVE. This is the highest-priority fix.

2. **Budget numbers in context-fundamentals are materially wrong.** Ambient load is ~1,000-1,270 lines, not ~600-700. The threshold guidance is still valid (percentage-based) but the worked example and breakdown are misleading.

3. **Claude-architect's own definition and memory have a stale agent count.** Says "six agents" -- should be seven (docs-writer added in E-028).

4. **Architect memory has stale deployment details.** References Hetzner VPS and Litestream, which were superseded by home Linux server and simple file backup.

5. **Dispatch-pattern agent selection table is missing docs-writer.** PM has no explicit routing guidance for documentation stories.

6. **General-dev and api-scout MEMORY.md files duplicate CLAUDE.md content.** Minor issue but violates the "reference CLAUDE.md, do not copy" principle.

### Key Metric

**Total ambient context per session: ~1,000-1,270 lines** (depending on agent). This is healthy for a 128k token context window but represents meaningful growth from the original ~600-700 line estimate. The growth is justified by real needs (new rules, fleshed-out agents) but the documented estimates should be updated to reflect reality.

---

## 10. Recommended Execution Plan

If this review is actioned as an epic:

1. **Single story for P1.x fixes**: Update PM MEMORY.md, architect MEMORY.md, context-fundamentals skill budget numbers, and architect agent definition. All are text edits to context-layer files -- route to claude-architect per dispatch-pattern.

2. **Single story for P2.x fixes**: Fix pii-check.sh comment, filesystem-context E-010 reference, dispatch-pattern docs-writer row, workflow-discipline paths cleanup. Mix of context-layer and hook files -- route to claude-architect.

3. **Optional story for P3.x**: Trim memory file duplication. Lower priority; could be deferred.

4. **P4.x**: No epic needed. These are observations for future reference.

Alternatively, all P1 and P2 fixes could be a single story since they are all small text edits with no dependencies between them.
