# E-228: Matchup Strategy Report (v1)

## Status
`READY`

## Overview
Add a "Game Plan" section to standalone scouting reports when the operator selects an LSB "us" team. The section combines opponent scouting with LSB-aware context (top-3 opposing hitters with per-hitter pitch-attack cues, pull-tendency notes, stolen-base profile, first-inning scoring tendency, 3-bucket loss recipe, eligible opposing pitchers, eligible LSB pitchers). Uses the existing two-tier pattern (deterministic engine + Tier 2 LLM narrative) established by predicted-starter. Existing single-team scouting reports remain byte-identical when the matchup option is unselected.

## Background & Context
LSB coaches currently produce game-day matchup strategy by hand. The architectural reference is E-212 predicted-starter: pure-function deterministic engine + LLM Tier 2 wrapper. The matchup section follows the same shape and slots into `src/reports/generator.py` parallel to the predicted-starter block.

This is **v1**. The original E-228 plan (5-reviewer consensus 2026-04-28) was over-scoped: 11 stories, ~700 lines of epic.md, three-gate starter prediction picking THE LSB starter, head-to-head sidebar, 4-template TL;DR slot-2 priority tree, 14 tunable constants, byte-identical baseline-fixture machinery, full visual hierarchy spec. The user steered v1 down to a minimal coach-useful surface and split everything else into follow-on epics (E-230, E-231, E-232). Plays-in-scout pipeline parity was split into its own independent epic (E-229) -- not a blocker for E-228 v1; see Plays Dependency below.

**Discovery consultations (2026-04-27, preserved from original planning):**
- **baseball-coach**: Locked the "argument not stat sheet" voice and the inline-citation rule for prescriptive claims. v1 delivers ONE mental cue per dangerous hitter (HS pitchers hold one cue under pressure; two is noise). 3-bucket loss recipe (HS reality: starter shelled / bullpen couldn't hold / close game lost late). Coach added pragmatism asks: stolen-base profile and first-inning scoring tendency.
- **api-scout**: 99% of inputs already in DB. API ceilings: pitch type / velocity / zone / defensive alignment / pitcher repertoire NOT exposed by GC. Plays exposes outcome-based pitch tendencies (FPS%, count-based outcomes, batted-ball type). Plays NOT auto-run in `bb data scout` -- needs wiring (now E-229).
- **software-engineer**: Path C (additive opt-in) is the lowest-risk lift -- 1-line schema migration + optional generator parameter + single conditional template section. Engine should follow pure-function discipline (all DB lookups in input builder; engine is pure). LLM prompt mirrors `llm_analysis.py`. Hallucination guardrail (player-name round-trip) non-negotiable.
- **claude-architect**: Light context-layer impact -- closure-time edits to `architecture-subsystems.md` (extend "Two-Tier Enrichment Pattern" to list matchup as second instance). Closure work, not story work.
- **data-engineer**: New helpers `get_top_hitters`, `get_hitter_pitch_tendencies`, `get_sb_tendency`, `get_first_inning_pattern`. Loss-recipe classification lives in engine, not query layer ("queries fetch facts; engine derives narratives"). Cross-perspective traps documented.

**User scope decisions (2026-04-28, v1 refinement):**
- Top-3 opposing hitters, NOT top-5. ONE mental cue per hitter, NOT two.
- Pull tendency notes (renamed from "defensive shifts" -- HS programs can't execute non-standard positioning; show the data, let coach decide).
- Stolen-base profile NEW (catcher CS-against rate + opponent SB%). First-inning scoring tendency NEW.
- 3-bucket loss recipe (NOT 5).
- Eligible opposing pitchers list -- light treatment, NO per-pitcher elaboration.
- Eligible LSB pitchers list when `our_team_id` set -- light treatment, NO prediction, NO override input.
- Head-to-head DROPPED ENTIRELY (don't play same team enough times at HS level).
- Three-gate LSB starter prediction DROPPED. LSB starter override input field DROPPED.
- LSB lineup card DROPPED (coach makes the lineup).
- Handedness DROPPED (already non-goal).
- Pitcher-predictions checkbox split DROPPED -- predicted-starter stays as-is.
- Single new "Game Plan" section. Path C (additive opt-in). `our_team_id` schema column nullable.

## Goals
- A coach generating a report for tomorrow's opponent can check "Include matchup section" + pick their LSB level and receive a prescriptive coach-voice Game Plan section alongside the existing scouting content.
- Every prescriptive recommendation (pitch-attack per hitter, pull-tendency notes) cites supporting data points inline.
- The deterministic engine produces a typed dataclass that the LLM Tier 2 narrative wraps without introducing player names or statistics not present in the input.
- Existing single-team scouting reports continue to generate identically when the matchup option is unselected.

## Non-Goals
- Three-gate LSB starter prediction (cut from v1; deferred to E-230 if reframed as "match eligible pitchers to recipe profile").
- LSB lineup card.
- Head-to-head sidebar (any form).
- LSB starter override input field.
- 4-template TL;DR slot-2 priority tree (deferred to E-230).
- Recent-form arrow overlay (deferred to E-230).
- 14 tunable-constants framework (deferred to E-230).
- decision_unknown 6th loss bucket + plays_loaded_per_game completeness surfacing (deferred to E-230).
- Print stylesheet hardening, mobile responsive at 375px, AVOID inline sub-bullet typography (deferred to E-231).
- Byte-identical baseline-fixture machinery (deferred to E-231; v1 uses lighter regression coverage).
- Plays auto-run in `bb data scout` (split into independent epic E-229; not a blocker for v1 -- see Plays Dependency).
- Dashboard parity (lighter matchup variant on opponent dashboard) -- deferred to E-232.
- Multi-LSB-team auto-disambiguation -- v1 does NOT attempt to guess which member team to use when an opponent appears under multiple member teams' `team_opponents`. Disambiguation is resolved by user selection of `our_team_id` in the admin form (or the `--our-team` CLI flag). When `our_team_id` is None, no matchup section renders regardless of opponent's `team_opponents` row count -- the existing skip-when-None rule (Success Criteria) covers this case.
- Pitcher-predictions checkbox split (predicted-starter stays always-on as today).
- Pitch-type / zone / velocity tendencies (API ceiling, permanent).
- Defensive alignment observed from opposing teams (API ceiling, permanent).
- Inning-by-inning game-plan narrative (judgment-heavy; out of v1).

## Success Criteria
- A coach checks "Include matchup section" + selects "LSB Varsity" + provides an opponent GC URL, and receives a generated report with both the existing scouting content AND a new Game Plan section containing 6 sub-sections in this order: (1) top-3 opposing hitters with one cue each (PA badges, inline citations) plus full-roster pull-tendency notes inline, (2) eligible opposing pitchers list, (3) stolen-base profile, (4) first-inning scoring tendency, (5) 3-bucket loss recipe, (6) eligible LSB pitchers list.
- Every prescriptive recommendation for pitch-attack per hitter and pull-tendency notes includes an inline data citation (e.g., "Tagge -- free swinger early (58% FPS, 62 PA), bury one in.") in the rendered output.
- The LLM Tier 2 narrative does NOT name any player not present in the deterministic dataclass; verified by structured tests.
- Generating a report WITHOUT the matchup option produces identical output to today (regression test passes).
- The matchup section does NOT render when `our_team_id` is None OR when `confidence == "suppress"` (no placeholder).

## Stories
| ID | Title | Status | Dependencies | Assignee |
|----|-------|--------|-------------|----------|
| E-228-01 | Path C lift: schema + generator parameter + admin checkbox + CLI flag | TODO | None | - |
| E-228-12 | Matchup engine + input builder: dataclasses, query helpers, `compute_matchup()`, `build_matchup_inputs()` | TODO | E-228-01 | - |
| E-228-13 | LLM Tier 2 wrapper: `enrich_matchup()` with hallucination guardrail | TODO | E-228-12 | - |
| E-228-14 | Generator orchestration + renderer + docs: wire matchup into `generate_report()`, single Game Plan section, coach + admin docs | TODO | E-228-01, E-228-12, E-228-13 | - |

## Dispatch Team
- software-engineer
- data-engineer
- docs-writer

## Technical Notes

### Architectural Path: C (Additive Opt-In)
Schema change (one column, nullable): `ALTER TABLE reports ADD COLUMN our_team_id INTEGER REFERENCES teams(id);`. Migration `migrations/002_add_our_team_id_to_reports.sql` (next available per `.claude/rules/migrations.md`). Existing rows have `our_team_id IS NULL`; the renderer hides the matchup section in that case.

`generate_report()` accepts an optional `our_team_id: int | None = None`. When provided, the generator builds matchup inputs, calls `compute_matchup()`, calls `enrich_matchup()` (Tier 2, non-fatal), and renders a Game Plan section. When None, the matchup section is not rendered.

### Two-Tier Mirror Reference
The matchup engine mirrors the predicted-starter pattern:
- `src/reports/matchup.py` -- `MatchupInputs` / `MatchupAnalysis` dataclasses + `compute_matchup()` (pure function) + `build_matchup_inputs()` (all DB queries here).
- `src/reports/llm_matchup.py` -- `enrich_matchup()` Tier 2 wrapper, mirrors `src/reports/llm_analysis.py` exactly (system prompt template, ASCII-table grounding, strict JSON output, hallucination ban, OpenRouter call parameters).

The hallucination guardrail (player-name round-trip check) is non-negotiable. The wrapper takes `(MatchupAnalysis, MatchupInputs)` together: inputs needed for the prompt's grounding tables; analysis needed for output structure.

### Suppress Semantics (One Behavior)
The matchup section is hidden -- with no placeholder -- in two cases that collapse to the same behavior:
1. `our_team_id is None` (structural skip; no LSB context, no matchup).
2. `our_team_id is set` AND opponent data is too thin to support analysis (engine returns `confidence="suppress"`).

In both cases, the existing scouting report renders identically to today and no Game Plan section appears. When opponent data is partial (some components thin, others not), per-component data-depth notes render alongside the available content; the section as a whole stays visible. The data-depth notes flow from `MatchupAnalysis.data_notes`, each tagged with a `subsection` field (per E-228-12 AC-1) that the renderer uses to place the note at the bottom of the corresponding sub-section as an italic gray "Note: ..." line (per E-228-14 AC-3). PA badges + "early read only" softening on top-3 hitter rows remain in-band per E-228-14 AC-3 sub-section 1.

### Perspective-Provenance Compliance
All matchup queries that read per-player stat tables (`player_game_batting`, `player_game_pitching`, `spray_charts`, `plays`) MUST filter by `perspective_team_id`. The standalone reports flow uses the opponent's team_id as the perspective for opponent stats. For LSB stats (when `our_team_id` is set), the perspective is the LSB team's id. Existing helpers in `src/api/db.py` already encode this; new helpers added in E-228-12 must follow the same pattern.

### Plays Dependency
**E-229 (plays-in-scout parity) is NOT a blocker for E-228 v1.** The opponent-side inline plays patch at `src/reports/generator.py:1091` already loads opponent plays before the query/render phase, which is what matchup v1 consumes (FPS%, count-based outcomes, chase rate, stolen-base profile). E-228 v1 does not consume LSB-side plays -- the eligible-LSB-pitchers list reads boxscore-derived data via `get_pitching_workload()`, not plays. E-229 remains independently valuable scout-pipeline hygiene work that benefits dashboards equally; if E-229 ships first, the opponent-side inline patch becomes redundant for reports (cleanup work). If E-228 v1 ships first, the inline patch stays in place until E-229 lands.

### Feature Flag
`FEATURE_MATCHUP_ANALYSIS` env var gates the new section, mirroring `FEATURE_PREDICTED_STARTER`. When unset or false, the admin checkbox is hidden, the CLI flag emits a "feature disabled" warning, and `generate_report()` ignores `our_team_id`. Default: enabled in dev, controlled by ops in prod.

### Closure Work (PM, Not a Story)
Per `.claude/rules/context-layer-assessment.md` and `.claude/rules/documentation.md`, the PM evaluates context-layer triggers and documentation triggers at archive time. Expected impacts: extend "Two-Tier Enrichment Pattern" in `architecture-subsystems.md` to list matchup as the second instance; user-facing doc pages for coach (`docs/coaching/matchup-report.md`) and operator (`docs/admin/matchup-report-generation.md`) ship in story E-228-14, not as closure work.

## Open Questions
1. **Multi-LSB-team `our_team_id` ambiguity**: Resolved for v1. The user-selected `our_team_id` (admin form dropdown or `--our-team` CLI flag) is always authoritative -- the engine and renderer use that team as the LSB perspective regardless of how many `team_opponents` rows the opponent has. When `our_team_id` is None, the matchup section is skipped entirely (per Success Criteria), so no auto-disambiguation logic is needed in v1. Head-to-head context is no longer relevant in v1 (head-to-head dropped). The eligible-LSB-pitchers list is scoped to the selected `our_team_id` only. May resurface in E-232 (dashboard parity) where the dashboard surface may need its own disambiguation.
2. **`compute_matchup()` vs `build_matchup_inputs()` story split**: v1 keeps both in a single story (E-228-12) because the engine's signal selection is tightly coupled to the helpers' return shapes. If during planning the boundary feels naturally splittable, E-228-12 can be broken into 12a (engine + dataclasses) and 12b (input builder + query helpers) without changing scope.

## History
- 2026-04-27: Created. Discovery consultations (baseball-coach, api-scout, software-engineer, claude-architect, data-engineer, ux-designer). User scope decisions: Path C, fresh-on-demand scout, three-gate starter prediction, plays-in-scout. 11 stories, ~700-line epic.md.
- 2026-04-27: Quality-bar revision. ACs reorganized into Behavior / Test Coverage / Documentation. New docs-writer story added (E-228-10). Files Touched matrix expanded. Test ACs hardened.
- 2026-04-27: Data-engineer refinement. E-228-04 reduced from 8 helpers to 3. Loss-recipe classification moved to engine. New `data_completeness` block. Pre-flight gate on opponent-perspective coverage. Conditional new index for `play_events` first-pitch lookups.
- 2026-04-27: UX layout incorporation + user decision B (independent checkboxes, no mutual exclusion).
- 2026-04-27: Phase 3 holistic review + triage (114 raw findings, 70 unique, 56 ACCEPT). Migration renumbering 016/017 → 002/003. Routing-precedence fix. K/9 → K/BB. Bullpen_burn ≥4 → ≥3. Per-day → last-N-games window. Section placement verbatim ordering.
- 2026-04-27: Coach P2-T resolution. 4-template TL;DR slot-2 priority tree codified. New module constants added.
- 2026-04-28: Refined down per 5-reviewer consensus (claude-architect, PM, baseball-coach, Explore, Codex) + user steering. Cut 7 stories' worth of scope. Dropped: head-to-head (any form), three-gate starter prediction, LSB starter override input, LSB lineup card, 4-template TL;DR slot-2 tree, recent-form arrow overlay, 14-constant tuning framework, decision_unknown 6th loss bucket, AVOID inline sub-bullet typography, byte-identical fixture machinery, dashboard parity, plays-in-scout (split to E-229). Added: stolen-base profile and first-inning scoring tendency per coach pragmatism check. Loss recipe simplified 5→3 buckets. Top hitters reduced 5→3. ONE mental cue per hitter (was two). Pitcher-predictions checkbox split removed -- predicted-starter stays always-on. Spec contradictions resolved: suppress hides without placeholder; `our_team_id=None` skips matchup entirely (no opponent-only degraded path); `data_notes` lives on `MatchupAnalysis` only; LLM wrapper takes `(MatchupAnalysis, MatchupInputs)` together. Story spine 11 → 4 (E-228-01 + new E-228-12, E-228-13, E-228-14). Stories 02-11 cut (files retained as CUT stubs pointing to this History entry). Follow-on epics created as DRAFT stubs: E-229 (plays in scout parity, blocks v1), E-230 (engine v2 coaching tunables), E-231 (visual polish + print hardening), E-232 (dashboard parity). Status returned to DRAFT pending re-spec-review.
- 2026-04-28: Codex re-review fixes: resolved 3 P1 + 2 P2 + 1 epic-level finding from spec review. Loss-recipe engine output narrowed to counts + grounding tuples (LLM produces prose). Suppress trigger restated as in-engine condition (`len(opponent_top_hitters) == 0 AND len(opponent_losses) == 0`) -- no new "coverage" signal field on `MatchupInputs`. Section order pinned: `Header → Exec summary → Game Plan → Predicted Starter → ... → Footer`; Game Plan goes BEFORE Predicted Starter when matchup renders. PullTendencyNote citation pattern uses raw `pull_pct` and `bip_count` fields directly (no `supporting_stats` field added). AC-T7 stale degraded-state branch removed -- suppress is the single behavior for missing LSB-side data. E-228-14 Agent Hint changed from `docs-writer` to `software-engineer` (file set is primarily code + tests + template). Multi-LSB-team contradiction resolved (user-selected `our_team_id` is always authoritative; v1 covered by existing skip-when-None rule -- no auto-disambiguation needed). E-229 blocking justification added to Plays Dependency section.
- 2026-04-28: Codex pass 2 cleanup -- propagation fixes localized to E-228-14 (AC-T7 trigger restated to match suppress contract from E-228-12 AC-13, stale "Shift LF" + `supporting_stats: list[StatCitation]` example in Technical Approach replaced with raw-field citation pattern, stale "docs-writer per Agent Hint" reference replaced with software-engineer text consistent with current Agent Hint).
- 2026-04-28: Codex pass 4 fixes -- corrected E-229 blocking rationale (sequencing-preferred, not data-required); added `opponent_roster_spray` field to `MatchupInputs` for full-roster pull-tendency notes; codified citation source-of-truth split (LLM cites prose claims via embedded parentheticals; renderer formats deterministic engine output citations like pull-tendency notes from raw fields).
- 2026-04-28: Codex pass 5 fixes -- removed E-229 as a blocker for E-228 v1. The active spec consumes only opponent-side plays (already loaded by the existing inline patch in `generator.py:1091`); LSB-side plays are not consumed by v1. E-229 remains independently valuable scout-pipeline hygiene. Removed `pull_tendency_prose` from LLM output schema (stale post-citation-source-of-truth split -- pull-tendency notes are deterministic engine output, not LLM prose).
- 2026-04-28: Codex pass 7 fixes -- clarified `game_plan_intro` rendering location and LLM-failure fallback for top-hitter rows in E-228-14; rewrote E-228-13 description to match the multi-field LLM output schema (no longer "single coach-voice paragraph"); replaced "early-vs-late game pattern" wording with "first-inning scoring tendency" across active prose; comprehensive drift sweep across all four active spec files for description-paragraph staleness against canonical contract state.
- 2026-04-28: Codex pass 8 fixes -- corrected stale sub-section numbering in E-228-14 AC-6 LLM-fallback bullets to match canonical 6-section order; specified data_notes rendering location for non-hitter sub-sections (italic gray line at bottom of corresponding sub-section per Option A; data_notes entries gain `subsection` field on MatchupAnalysis schema).
- 2026-04-29: Status flipped to READY. The 2026-04-28 "returned to DRAFT pending re-spec-review" transition was resolved by Codex passes 2/4/5/7/8 on 2026-04-28; this entry closes the bookkeeping gap. Light-touch verification confirmed the active spec (epic + E-228-01/12/13/14) is internally consistent: section ordering pinned (Header → Exec summary → Game Plan → Predicted Starter → ...); suppress contract identical across epic Technical Notes / E-228-12 AC-13 / E-228-14 AC-5+T7 / E-228-13 AC-2 (`len(opponent_top_hitters) == 0 AND len(opponent_losses) == 0`); citation source-of-truth split consistent (LLM cites prose; renderer formats deterministic citations only for pull-tendency notes); `pull_tendency_prose` removed from LLM schema; Plays Dependency settled (E-229 NOT a blocker for v1). Codex pass 8 fixes verified applied across all 4 active spec files. Two stale CUT-stub assertions also corrected on 2026-04-29 (Path B alignment, no scope change): E-228-02 line 7 ("v1 of E-228 depends on E-229") replaced with current-state pointer to Codex pass 5 reversal; E-228-07 line 7 ("single coach-voice paragraph") replaced with multi-field JSON schema per Codex pass 7.
- 2026-04-29: Review scorecard for E-228 (reconstructed from prior History entries). Pre-refinement Phase 3 holistic review (2026-04-27, line 122): 114 raw findings, 70 unique, 56 ACCEPT -- migration renumbering, routing-precedence fix, K/9→K/BB, bullpen_burn ≥4→≥3, per-day→last-N-games window, section placement verbatim ordering. Post-refinement Codex passes (all on 2026-04-28): pass 1 (line 125) -- 3 P1 + 2 P2 + 1 epic-level finding resolved (loss-recipe engine output narrowed to counts + grounding tuples; suppress trigger restated as in-engine condition; section order pinned; PullTendencyNote citation pattern uses raw fields; AC-T7 stale degraded branch removed; E-228-14 Agent Hint changed to software-engineer; multi-LSB-team disambiguation resolved; E-229 blocking justification added). Pass 2 (line 126) -- 3 propagation fixes localized to E-228-14 (AC-T7 trigger restated to match suppress contract; stale "Shift LF" + `supporting_stats: list[StatCitation]` example replaced with raw-field citation pattern; stale "docs-writer per Agent Hint" reference replaced with software-engineer text). Pass 4 (line 127) -- 3 fixes (E-229 blocking rationale corrected to sequencing-preferred; `opponent_roster_spray` field added to `MatchupInputs`; citation source-of-truth split codified). Pass 5 (line 128) -- 2 fixes (E-229 removed as blocker for v1; stale `pull_tendency_prose` removed from LLM output schema). Pass 7 (line 129) -- 4 fixes via comprehensive drift sweep (`game_plan_intro` rendering location + LLM-failure fallback for top-hitter rows; E-228-13 description rewritten to match multi-field LLM output schema; "early-vs-late game pattern" replaced with "first-inning scoring tendency" across active prose; description-paragraph staleness sweep across all 4 active spec files). Pass 8 (line 130) -- 3 fixes (stale sub-section numbering corrected in E-228-14 AC-6; `data_notes` rendering location specified for non-hitter sub-sections; `subsection` field added to MatchupAnalysis schema). Total post-refinement: 18 distinct findings resolved across 6 Codex passes; final state quiescent since pass 8.
