---
name: pitcher-outings-scouting-consultation
description: Domain consultation on pitcher outings-breakdown section for opponent scouting reports (feature-flagged) -- stat ranking, highlight direction, log-vs-summary tiering, ERA basis defect ruling
metadata:
  type: project
---

Consultation (2026-07-15) on a prototype pitcher outings-breakdown section (`pitcher-outings.md`, report `GJIwSMR_OKij4uJo`, Post 84 Columbus Cornerstone) for the SCOUTING report surface -- reader is the coach preparing to FACE this staff, not the staff's own coach. Feature is feature-flagged; api-scout ruling feasibility separately (velocity/pitch-mix already ruled out as unavailable).

## Why: PM/UX asked for coaching judgment on stat selection, highlight color direction, and artifact shape independent of feasibility, to intersect with api-scout's ruling afterward.

## Stat priority ranking (opponent-scouting frame, not own-team frame)

MUST HAVE: FPS% (approach-changing -- take vs. hack on 0-0), BB rate, K/9 or K%, H allowed rate/BAA, HR/XBH allowed, recent workload (already owned by Most Likely Arms card -- don't duplicate).

SHOULD HAVE: K/BB ratio (best single quality read at this level), GO/AO or GB/FB% (drives bunt/steal calls), WHIP (season shorthand), ERA (expected headline number despite being the least process-informative stat here -- results-based, defense-dependent).

NICE TO HAVE: leadoff-out%, <3-pitch PA%, 1-2-3 innings, BABIP, BA/RISP -- all need explicit small-sample caveats, RISP especially (often single-digit PA per pitcher per season).

SKIP: velocity, pitch mix, granular LD/FB/GB splits -- agrees with api-scout's feasibility call independently: even if available, these staffs' sample sizes (many arms under 15 IP) make fine-grained splits noise, not signal.

## Highlight-direction ruling (green shading rejected)

Green shading for "strong performances" is backwards on an OPPONENT report -- green reads as good, but the coach is hunting weakness to exploit, not admiring the opponent's best outings. Ruled:
- Drop green from this section entirely; reserve green for LSB's own-team reports where good-for-them = good-for-us.
- Two-signal highlighting: exploit signal (red/amber -- hittable/wild outings, what the coach is hunting for) vs. respect signal (neutral marker -- bold border/gray/icon, NOT a color reading as good news, still needs surfacing so the coach doesn't get cute against a dominant arm).
- Illustrative starting thresholds (SE/DE to validate against real distributions): exploit flag when BB>=4, FPS%<40%, XBH allowed>=3, or R>=6 in an outing; respect flag when 0 BB across 3+ IP, FPS%>=65%, K>=2/3 of BF, or 0 ER across a 4+ IP start.
- Sample floor before flagging: BF>=10 or IP>=2 -- below that, badge the count but don't color-flag (a 0.2-IP mop-up appearance shouldn't get either flag).
- Never suppress or dim regardless of sample -- badge PA/IP counts, consistent with `.claude/rules/display-philosophy.md`.

## Artifact shape: tiered by report-consumption mode, not one format

- Printable bench one-pager: season summary line only (one row/pitcher) + a "last 3 outings" recent-form mini-line for the 2-3 probable/likely starters (cross-ref Most Likely Arms card). No full per-outing log -- too dense for a B&W bench card.
- Pre-game scouting review (30-min pre-first-pitch read): full per-outing log, but ONLY for probable/likely starters. Relief-only arms get season-line-only.
- Quick lookup: season summary numbers only.
- Trimmed per-outing column set (18 -> ~11): Date | Opponent | IP | BF | H | HR | BB | K | R | FPS% | ERA(game). Dropped: Result (team result != pitcher performance and can mislead), S (start flag, fold into grouping), #P (owned by workload card, don't duplicate), S% (redundant with the more actionable FPS%), 2B/3B broken out separately (combine into XBH if wanted; HR stays distinct -- strategically different). Keep R over ER per row (actual damage inflicted matters more to the lineup than defense-adjusted ER; ER still drives the season ERA calc).

## ERA basis -- ruled a real defect, not cosmetic

Reports currently compute 9-inning ERA (ERx27/outs) for ALL teams; GameChanger displays 7-inning ERA (ERx21/outs) for HS/youth-length games -- verified ~29% overstatement vs. what a coach already sees in GC's own app for the same team.

Ruling: MUST match the league-regulation basis GameChanger itself displays for that team's level (7-inning for HS/youth-length games, 9-inning for senior Legion/adult-length games) -- not a flat 9-inning formula everywhere. This is a MUST FIX bundled into (or preceding) the outings-breakdown work, not deferred: the per-outing log multiplies the wrong-basis problem across every game row, and a wrong headline number on the most-scanned pitching stat undermines trust in the whole report. Ties directly to the project's stated North Star (byte-identical fidelity vs. GameChanger's official numbers, CLAUDE.md).

Scope note: WHICH basis applies to a given team is a detection/schema question, routed to data-engineer/software-engineer -- not a coaching call. Flagged that the project already has a league x level x phase gate for pitch-count rules ([[league-pitch-rules]]) as reuse precedent for keying the ERA-basis decision rather than inventing a second convention.

## Status
Consultation delivered as a recommendation; became epic E-265 (Pitcher Outings Breakdown). See [[e265-krate-and-highlight-ruling]] for the follow-on IDEA-141 K-rate decision and the locked green-only highlight thresholds ruled during E-265 refinement (2026-07-15).
