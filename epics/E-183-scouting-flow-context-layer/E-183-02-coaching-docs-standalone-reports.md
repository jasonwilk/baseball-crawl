# E-183-02: Add Standalone Reports to Coaching Docs

## Epic
[E-183: Codify Opponent Flow vs Reports Flow in Context Layer](epic.md)

## Status
`TODO`

## Description
After this story is complete, the coaching documentation will cover the standalone reports feature so coaching staff know it exists, how to request one, and how to use the link they receive. This closes the gap where `docs/coaching/scouting-reports.md` covers the coaching dashboard but does not mention standalone reports.

## Context
`docs/coaching/scouting-reports.md` covers the full coaching dashboard (schedule view, batting/pitching tabs, opponent scouting pages, spray charts, print views) but does not mention standalone reports. Coaching staff who receive a standalone report link have no documentation explaining what it is, how long it lasts, or how it differs from the dashboard. This story adds that coverage -- either as a new section in the existing file or as a companion file, at the implementer's discretion.

## Acceptance Criteria
- [ ] **AC-1**: Coaching docs explain what standalone reports are -- a shareable link to a frozen scouting snapshot generated on demand by the operator -- and when to ask for one (e.g., scouting a team not yet on the schedule, quick pre-game report for an assistant coach)
- [ ] **AC-2**: Coaching docs explain how to use a standalone report: open the link, view on phone or laptop, print via browser print command
- [ ] **AC-3**: Coaching docs note that reports expire after 14 days and that the link will stop working after expiry (the system returns a 404, not a friendly page -- just say "the link will no longer work")
- [ ] **AC-4**: Coaching docs distinguish standalone reports from the dashboard opponent view: standalone reports are frozen snapshots anyone can open; the dashboard shows live data requiring login. The new content must use the term "standalone report" (not "scouting report") when referring to the reports flow, per the naming convention in TN-2
- [ ] **AC-5**: The doc includes a "Last updated: YYYY-MM-DD" date and "Source: E-183" reference near the top of the new content, per the staleness convention in `/.claude/rules/documentation.md`
- [ ] **AC-6**: If a companion file is created (rather than adding a section to the existing file), `docs/coaching/scouting-reports.md` includes a cross-reference link pointing coaches to the new file

## Technical Approach
Read the existing `docs/coaching/scouting-reports.md` to understand the current style and structure. Add standalone reports coverage in a way that complements the existing content. The audience is coaching staff (non-technical) -- use the same plain language style as the existing doc. Coverage scope is defined in TN-5 of the epic.

## Dependencies
- **Blocked by**: None
- **Blocks**: None

## Files to Create or Modify
- `/workspaces/baseball-crawl/docs/coaching/scouting-reports.md` (add section to existing file)
- `/workspaces/baseball-crawl/docs/coaching/standalone-reports.md` (alternative: new companion file -- at implementer's discretion, one or the other)

## Agent Hint
docs-writer

## Definition of Done
- [ ] All acceptance criteria pass
- [ ] Documentation follows coaching docs style (plain language, non-technical audience)
- [ ] Code follows project style (see CLAUDE.md)
