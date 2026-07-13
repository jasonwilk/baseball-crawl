# E-263-09: Coaching how-to — Deep Scout product reference

## Epic
[E-263: Deep Scout v1 — Opponent-Intelligence Report Sections](epic.md)

## Status
`TODO`

## Description
After this story is complete, a coaching how-to in `docs/coaching/` explains what the new Deep Scout report sections tell a coach and how to act on each — the product reference that consumes the shipped v1 subset, distinct from the living engineering/coaching catalog.

## Context
claude-architect drew the line during consultation: the living signal catalog (`.project/research/scouting-signal-catalog.md`) is a growing engineering+coaching spec that stays in `.project/research/`; the `docs/` product reference is a NEW, smaller coaching artifact that consumes only the built subset. That is this docs-writer story. The audience is the coaching staff (report consumers), consistent with the docs-writer charter for `docs/coaching/`. It documents the four shipped sections (Technical Notes TN-5) in plain coaching language, honoring the ethics framing (coach-facing named materials; player-facing is v2). It must describe the sample-floor/grey-state honesty (a `thin`/`no_data` state means "not enough games yet," not "no tendency") so coaches read the trust surface correctly.

## Acceptance Criteria
- [ ] **AC-1**: A new coaching how-to under `docs/coaching/` documents the four Deep Scout sections (Tonight's Game Plan, Who's Pitching, Their Hitters & Defense, Running Game & Battery per Technical Notes TN-5), each with what it tells the coach and the in-game/practice action it drives.
- [ ] **AC-2**: The doc explains the trust surface in coaching terms per Technical Notes TN-2: a `thin` stat means "not enough games yet — this is a lean, not a lock" (the number is still shown), distinct from `no_data` which means "we can't compute this at all yet" (structural absence); the number is never dimmed or hidden by sample size; and raw counts appear for sparse events (e.g. backpicks) — so a coach does not over- or under-read a thin signal.
- [ ] **AC-3**: The doc explains the probable-starter conditioning in plain terms — that the game plan is built around the arm expected to pitch (and what the "committee" state means), and that the catching card is plays-derived (a scouting estimate, distinct from official box-score stats) per Technical Notes TN-7.
- [ ] **AC-4**: The doc is written for the coaching-staff audience (not operators) and describes only what shipped in v1 — no promises about the v2 player-facing One Card or LLM narrative.
- [ ] **AC-5**: Content is verified against the shipped report (the sections, labels, and states the coach actually sees), not the plan.

## Technical Approach
docs-writer reads the shipped report template and the design doctrine (`.project/research/deep-scout-design-2026-07-12.md` §6 consumption verdicts, §8x for the concrete coaching examples that make the sections legible) and writes the how-to at the coaching-staff reading level. Place it under `docs/coaching/` per the docs-writer charter. Keep it a consumption reference (how to act on the report), NOT an engineering spec (the catalog remains that).

## Dependencies
- **Blocked by**: E-263-04, E-263-05, E-263-06, E-263-07 (the shipped sections it documents)
- **Blocks**: None

## Files to Create or Modify
- `docs/coaching/<deep-scout how-to>.md` (new — coaching product reference; docs-writer names it)

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Content verified against the shipped report, not the plan
- [ ] Written for the coaching-staff audience (see docs-writer charter)
- [ ] No regressions in existing tests

## Notes
Distinct from E-263-08 (the CA catalog activation): this is the coach-audience product reference; the catalog is the engineering/coaching spec. Both consume the same shipped subset but serve different readers and live in different trees (`docs/coaching/` vs `.project/research/`).
