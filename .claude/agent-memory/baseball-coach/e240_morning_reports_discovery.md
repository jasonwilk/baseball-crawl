---
name: e240-morning-reports-discovery
description: E-240 Epic E discovery consultation — expiry semantics, three-way outcome, scheduled report UX requirements, hard gates vs soft flags
metadata:
  type: project
---

## E-240 Morning-of-Game Scheduled Reports — Coach Discovery (2026-06-17)

Consulted during discovery for Epic E (ROADMAP §5 slice E). Produced structured findings for PM synthesis.

### Decision 1: Expiry Semantics — Option (a) Recommended

Extend expiry for scheduler-generated reports (45 days or season end). Reject "latest report per opponent" stable URL (Option b).

**Why Option b fails:** Reports are frozen snapshots for a specific game. A stable URL that resolves to the "latest" report conflates multiple games against the same opponent — the coach sees different data than what was sent to them. Frozen snapshot = the value. Extension just prevents 404 on a still-valid artifact.

**Implementation hint:** Conditional at `reports` INSERT: if `source = 'scheduled'`, set `expires_at = generated_at + 45 days` (or season end if derivable).

### Decision 2: Three-Way Outcome Surfacing

| Outcome | Operator | Coach |
|---|---|---|
| auto-resolved | Run record, no action | Email with link + game details |
| unresolved-but-mappable | ACTION REQUIRED alert email + copy-paste map-opponent command in CLI output | No email — silence is correct |
| no GC presence | Run record "no report possible" | Explicit explanation email: "they do not appear to use GameChanger" |

Coaches must never be silently surprised. The two failure modes: unresolved with no email, and a sent link to an empty/broken report.

**6am cron is correct for standard HS/Legion weekday games (4–7 PM starts).** Exception: Saturday tournament 9am starts — operator must run morning-before. Operator runbook item, not a code change.

### Decision 3: Scheduled Report Email Requirements

The fundamental difference vs. on-demand: no operator eyeballed it before the coach sees it. The email must carry that provenance gap.

**MUST HAVE in email:**
- Subject: opponent + date + team (e.g., "Scouting Report — Bellevue West · June 18 · LSB Varsity")
- Body: game context + coverage summary BEFORE the link ("Through June 15 · 12 of 14 games · Pitch detail for 10 games · Spray available")
- "Auto-generated this morning" provenance line

Coverage summary in the email body is non-negotiable. Coaches get the link on their phones at 7am — they need the trust check before clicking.

**SHOULD HAVE in report HTML header:**
"Generated for: LSB Varsity vs Bellevue West — June 18, 2026" — identifies the specific game context.

### Decision 4: Hard Gates vs Soft Flags

**Hard gates (do not generate, do not send link):**
1. Zero completed games (M=0 or N=0 loaded) — send explicit "no games yet" email, no link
2. All boxscores blocked (E-236 SQ1) — operator alert, nothing to coach
3. Unresolved placeholder opponent (TBD/TBA/etc.) — re-poll; treat as unresolved-but-mappable if still unresolved at run time

**Soft flags (generate, signal in email + footer):**
1. Low coverage <50%: put in email subject line "Scouting Report — Bellevue West [LIMITED DATA: 3 of 14 games]"
2. Name-only identity match: add email body note "team identity matched by name only — verify"
3. Spray unavailable: footer handles it, no email change
4. K=0 pitch detail: footer handles it ("No pitch-detail data")

**Wrong-opponent risk mitigation (MUST HAVE):**
Dry-run output must show the RESOLVED team name and location alongside opponent text:
```
Varsity vs "Bellevue West"  [opponent_id: a1b2c3]
  → RESOLVED: Bellevue West HS (Bellevue, WA)  [public_id: abc123xyz]
  → 12 games on record
```
Operator verifies the name is correct before trusting the mapping. One-time human check that prevents the wrong-team-forever failure mode.

### Vision Signals Noted

- Coach email with key stat summary (not just link) — top 2 pitchers, OBP, steal rate in email body
- Pre-season dry-run as Opening Day ritual to pre-resolve all opponents
- "Regenerate now" button on admin page for manual refresh of a scheduled report
