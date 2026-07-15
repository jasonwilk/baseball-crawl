---
name: e264-era-basis-scope-consultation
description: E-264 ERA-basis fix -- fallback/default ruling and K/9-vs-K/G scope decision (keep K/9 out of E-264)
metadata:
  type: project
---

Consultation (2026-07-15) on E-264, a scouting-report fix for ERA computed on a hardcoded 9-inning basis (`ER x 27/outs`) vs. GameChanger's actual per-team-season game-length basis (`innings_per_game`, observed values 6 or 7, default 7; `ER x (innings_per_game x 3)/outs`). Follows directly from the ERA-basis defect ruling in [[pitcher-outings-scouting-consultation]].

## Fallback/default ruling

When `innings_per_game` is unknown for a team (field missing/null), default to **7**, not 9 -- matches HS/youth (our primary population) and is the modal value across leagues served. Key off GameChanger's own per-team field rather than a hardcoded league map (reuse the per-league/level gating precedent from [[league-pitch-rules]]). Whatever basis is used, the report MUST visibly flag when it's a fallback/assumed basis next to the ERA number -- never a silent assumed-basis number (display-philosophy: never suppress, always contextualize).

## K/9 scope decision -- keep OUT of E-264

Same code lines that compute ERA (`x27`) also compute an invented K/9 stat (`SO x 27/outs`) -- not a real GameChanger stat (GC has no K/9; it has K/G = `innings_per_game x SO/IP`, also game-length-scaled). PM asked whether E-264 should also rebase K/9 to game-length (relabel "K/G") alongside the ERA fix, since it's a trivial parallel edit at the same site.

**Ruled: leave K/9 exactly as-is (traditional 9-inning basis) in E-264.** Reasoning:
- The ERA fix is a MUST FIX specifically because GameChanger's own app ALSO displays "ERA" for the same team -- a wrong-basis ERA is a visible, checkable contradiction of a number the coach already trusts (the project's byte-identical-fidelity North Star, CLAUDE.md). K/9 has no GC-displayed equivalent to contradict, so that specific fidelity argument does NOT transfer to K/9.
- Coaches specifically expect/benchmark K/9 on its traditional 9-inning, externally-portable basis -- it's the number used in recruiting conversations, scouting sites, and broader baseball media ("8+ K/9 is a dominant arm"). Silently rebasing to K/G shrinks the number relative to that external benchmark and risks misleading a coach evaluating a player's recruiting profile against outside comparisons.
- A coach scanning a report does NOT cross-check denominators between ERA and K/9 for internal coherence -- each rate stat is read against its own independent mental benchmark. The mismatched-basis-on-one-page concern is an analyst worry, not a coaching-usability problem.
- The pitcher-outings epic (see [[pitcher-outings-scouting-consultation]], MUST HAVE "K/9 or K%", SHOULD HAVE "K/BB ratio") is already slated to redesign the full pitching-stat presentation for that surface -- that's the right place to make the deliberate, holistic K-rate call (K/9 vs. K/G vs. K/BF vs. K/BB together), not a piecemeal edit riding along on the ERA-basis bugfix. Flagged to PM to make sure that epic's scope explicitly picks up "decide the K-rate stat basis/set" so it isn't dropped between the two epics.

If GC's K/G is ever surfaced, it should be an ADDITION with its own clear label, not a silent replacement of the K/9 number coaches already benchmark against.

## Exact basis-disclosure copy (delivered verbatim for story ACs)

Ruled: show the basis indicator on EVERY ERA, not only the assumed/fallback case -- a report can put an LSB pitcher's ERA next to an opponent's, and the two teams' `innings_per_game` values are not guaranteed to match (7 vs 6), so even a *known*-basis pairing needs the label or a coach gets no signal the comparison needs adjustment.

Placement: on the pitching table's ERA column HEADER, once per team's table (basis is a team-level constant -- repeating per pitcher row is clutter, not information). Inline-per-value is the fallback shape only if the table structure mixes two teams' pitchers with no per-team subheader to hang it on.

Exact strings:
- Header, known basis: `ERA (7-inn)` (substitute fetched value, e.g. `ERA (6-inn)`)
- Header, assumed/fallback basis: `ERA (7-inn)*`
- Footnote (assumed case only, once per table): `* Game length not available from GameChanger for this team -- ERA assumed on a 7-inning basis.`
- Inline fallback shape: `4.50 (7-inn)` / `4.50 (7-inn)*` with the same footnote

Wording choices: "assumed" (not "estimated"/"default"/"?") for plain-English no-decode-required reading; "-inn" abbreviation in the compact form for column-width fit, footnote spells out "inning" in full; never expose the raw field name `innings_per_game` user-facing -- footnote says "game length."

## Status
Recommendation delivered to PM during E-264 planning (2026-07-15): fallback=7 keyed off the per-team field, basis-note AC required (always-shown, header-level, exact copy above), K/9 left untouched and out of scope for E-264.
