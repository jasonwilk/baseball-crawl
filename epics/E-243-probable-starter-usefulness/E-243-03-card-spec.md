# E-243-03 Card Spec — "Most Likely Arms" (ux-designer)

Authoritative design input for E-243-03. The software-engineer implements the probable-starter section of
`src/api/templates/reports/scouting_report.html` (currently ~lines 508-654, the "Predicted Starter" block) against
this spec rather than re-deriving layout. Engine enrichment fields (`start_share_pct`, `days_rest`,
`rest_eligibility`, `throws`, `unavailable_arms`) are produced in `src/reports/starter_prediction.py` per E-243-03's
Technical Approach; this document specifies how they render.

**Stack reality:** this is the frozen-HTML scouting report, NOT the Tailwind dashboard. The report uses self-contained
CSS in `pt` units with `break-inside: avoid` for print/PDF. Design within the existing `.starter-card*` class idiom —
do NOT introduce Tailwind here. Escape all user-controlled values per `.claude/rules/jinja-safety.md`. Contextualize,
never suppress, per `.claude/rules/display-philosophy.md`.

**Context of use:** game-morning, ~10-second read on a phone (game-prep mode). Name + rest state must be scannable
without reading the reasoning line.

---

## 1. Section framing (AC-1, AC-4 — kill the committee hedge)

- **Heading:** `Most Likely Arms` — unchanged across estimate and non-estimate states (replaces "Predicted Starter").
- **Optional sub-label** (neutral, never an apology): `Likeliest starter(s) for this matchup — usually one of these.`
- **Rotation pattern** stays, but reframed as *context*, not a hedge, and placed BELOW the ranked list:
  - OLD: `committee — multiple candidates` (opens apologetically)
  - NEW: small gray annotation under the list — `Staff usage: committee (no dominant ace)` / `Staff usage: 2-man rotation` / `Staff usage: 3-man rotation`
- No rendered state opens with a "true committee situation"-style hedge.

---

## 2. Ranked likely-arms layout (AC-1, AC-2)

Vertical ranked list, top 2-3. #1 is visually primary (existing `starter-card-primary` left border); #2/#3 are
secondary cards.

### ASCII wireframe (375px / mobile-first; print mirrors it)

```
  Most Likely Arms
  Likeliest starter(s) — usually one of these.
  ┌──────────────────────────────────────────────┐  ← primary (thick left border)
  │ 1  J. Martinez (RHP)            [Ready ✓]     │
  │    8 of 30 starts (27%) · 5d rest             │
  │    Next in 2-man rotation; threw 62p Jun 22.  │  ← reasoning (existing)
  │    Date    IP   #P   K                         │  ← recent_starts mini-log (existing, optional)
  │    Jun 22  5.0  62   7                         │
  └──────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────┐  ← secondary (thin border)
  │ 2  T. Reyes (LHP)               [Short rest]  │
  │    6 of 30 starts (20%) · 2d rest (prefers 4) │
  │    Spot starter; lefty matchup option.        │
  └──────────────────────────────────────────────┘
  ┌──────────────────────────────────────────────┐
  │ 3  K. Boyd                      [Ready ✓]     │
  │    4 of 30 starts (13%) · 6d rest             │
  └──────────────────────────────────────────────┘
  Staff usage: 2-man rotation
  ── Unavailable today ──────────────────────────
  • C. Diaz — threw 95p Jun 24, needs 4 days rest
  ── Rest / Availability table (unchanged, AC-7) ──
  ...existing starter-rest-table...
  ── Bullpen order (unchanged) ──
  Based on rotation pattern, rest days, recent workload. Actual starter may differ.
```

### Per-line field hierarchy (left→right, top→bottom)

1. **Rank number** (1/2/3) — cheap visual ordering cue.
2. **Name + handedness** — `(RHP)` / `(LHP)` inline after the name, shown ONLY when `throws` is present; omit
   silently when absent. (`throws` is schema-ready but sparsely populated; treat as optional.)
3. **Eligibility chip**, right-aligned on the name row — the single most scannable element. **Two-valued only:**
   - `available` → green chip `Ready` (✓)
   - `discounted` → amber chip `Short rest`
   - Never "unavailable" on a ranked line — see §3.
4. **Stat sub-line** (one line): start-share + days-rest.
   - **Start-share grounded in GAMES, not a bare percent** (coaches think in games — CLAUDE.md Data Philosophy):
     `8 of 30 starts (27%)`, where `start_share_pct = round(games_started / total_team_games * 100)`. The `%` is
     secondary context in parens.
   - **Days rest:** `5d rest`. For `discounted`, append the why: `2d rest (prefers 4)` (preferred threshold from
     E-243-01's computation). If `days_rest` is unknown, show `rest unknown` — see note below.
5. **reasoning line** (existing `starter-card-reasoning`, unchanged).
6. **recent_starts mini game-log** (existing, optional, behind the same `{% if cand.recent_starts %}` guard; 3 rows).

> **Null pitch count / M1 (IP proxy):** per E-243-01 (M1 ruling), a candidate whose most-recent-day pitch count is
> null is IP-proxied and may classify as `discounted`. It still renders with the normal two-valued chip. **No per-arm
> estimate marker** is added (epic TN-5 / IDEA-083) — the section-level estimate treatment (§4) covers the common
> youth/travel case; a residual non-estimate-section case is cosmetic-only (the proxy still discounts correctly, so
> ranking is never wrong). SE must NOT invent a per-arm chip variant.

---

## 3. "Unavailable today (and why)" sub-block (AC-3)

Hard-excluded (unavailable) arms are NOT in `top_candidates` — the engine pops them from the candidate pool
(`starter_prediction.py` exclusion gate), so they can never be a ranked line. They render in their own sub-block,
fed by the new additive engine field `unavailable_arms: list[{name, reason}]` (the engine's existing exclusion reason
strings). This is where a coach learns "their ace is out today."

```
  ── Unavailable today ──
  • C. Diaz — threw 95p Jun 24, needs 4 days rest
  • M. Lowe — 3 appearances in last 3 days
```

- Each entry: `name` + the engine's exclusion `reason` string.
- Rendered ONLY when `unavailable_arms` is non-empty; omit the entire block (header included) otherwise — no empty header.
- Style: muted/red text; strike-through on the name is optional (matches the existing bullpen-order unavailable styling).

---

## 4. Estimate treatment — youth/travel (AC-5)

When the prediction carries `is_estimate == True` (from E-243-02), label it so a coach trusts it appropriately
without overstating it. Principle: **consequence-oriented labels** (E-178) — tell the coach what it MEANS for the
decision, not the internal source. **Option A (ratified):** the heading stays clean; the estimate signal is carried by
a badge + a one-line banner.

```
  Most Likely Arms   [Estimated rest]            ← amber pill on the heading
  ┌ Rest estimated ───────────────────────────────┐
  │ This level doesn't publish pitch-count rules,  │
  │ so rest and availability use a standard youth  │
  │ pitch-count guide. Treat as a directional read,│
  │ not a hard rule.                               │
  └────────────────────────────────────────────────┘
```

- **Heading badge:** `Estimated rest`
- **Banner copy (exact):** `This level doesn't publish pitch-count rules, so rest and availability use a standard
  youth pitch-count guide. Treat as a directional read, not a hard rule.`

### Absolute no-jargon rule (no carve-out)

Brand/source terms — **"Pitch Smart", "Legion", "USA Baseball", "soft prior"** — MUST NOT appear anywhere a coach
reads: not in the heading, not in the badge, not in the banner, not in the LLM narrative (E-243-04 AC-3 extends this
same rule to the rendered prose). The brand name lives ONLY in the code constant (`PITCH_SMART_15_18`), the
baseball-coach model doc, and internal LLM prompt context. Rationale: a coach hitting "Pitch Smart" on game morning
learns nothing about what it means for the decision.

- The badge appears **only** on estimates — its absence is the full-confidence signal for NSAA/Legion (binding-rule)
  reports. (Mirrors the E-178 opponent-badge approach: badge presence = a caveat; default = trusted.)
- The eligibility chips (§2) still render normally under the estimate frame — the section-level banner reframes the
  whole section, so chips don't each need their own caveat.
- The word is **"estimate"**, not "uncertain".

---

## 5. Suppress / not-enough-data state (AC-6)

When the engine returns `confidence == "suppress"` (too few games, or genuinely no rules), render the honest
data-note, softened (E-178 — "aren't ready yet", not "not loaded"):

> `Not enough games yet to project likely arms — rest data still accumulating.`

The rest/availability table and bullpen order still render below if data exists (AC-7). Never fabricate a ranked list
in this state.

---

## 6. CSS / HTML reference (report pt-unit idiom — extends existing classes)

New classes (add near the existing `.starter-card` block, ~line 335 of `scouting_report.html`):

```css
.starter-rank { display:inline-block; font-weight:bold; font-size:9pt; color:#6b7280; margin-right:4px; }
.rest-chip { float:right; font-size:7pt; font-weight:600; border-radius:3px; padding:0 5px; }
.rest-chip-ready { color:#065f46; background:#d1fae5; }
.rest-chip-short { color:#9a3412; background:#ffedd5; }
.starter-stat-line { font-size:8pt; color:#6b7280; margin-top:1px; }
.starter-estimate-badge { font-size:7pt; font-weight:600; color:#92400e; background:#fef3c7; border:1px solid #fcd34d; border-radius:3px; padding:0 4px; margin-left:6px; vertical-align:middle; }
.starter-estimate-banner { font-size:8pt; color:#92400e; background:#fef3c7; border:1px solid #fcd34d; border-radius:3px; padding:3px 6px; margin:4px 0 6px; }
.starter-unavailable { font-size:8pt; color:#991b1b; margin-top:6px; }
.starter-unavailable-label { font-weight:600; text-transform:uppercase; font-size:7pt; letter-spacing:.04em; color:#6b7280; }
```

Heading + estimate frame:

```jinja
<h2 class="section-header">Most Likely Arms{% if starter_prediction.is_estimate %} <span class="starter-estimate-badge">Estimated rest</span>{% endif %}</h2>
{% if starter_prediction.is_estimate %}
<div class="starter-estimate-banner">This level doesn't publish pitch-count rules, so rest and availability use a standard youth pitch-count guide. Treat as a directional read, not a hard rule.</div>
{% endif %}
```

Per-line markup (escape all user values). #2/#3 are identical minus `starter-card-primary` and the rank number:

```jinja
<div class="starter-card starter-card-primary">
  <div class="starter-card-name"><span class="starter-rank">1</span>{{ cand.name | e }}{% if cand.throws %} ({{ cand.throws | e }}){% endif %}
    <span class="rest-chip rest-chip-{{ 'ready' if cand.rest_eligibility == 'available' else 'short' }}">{{ 'Ready' if cand.rest_eligibility == 'available' else 'Short rest' }}</span></div>
  <div class="starter-stat-line">{{ cand.games_started }} of {{ total_team_games }} starts ({{ cand.start_share_pct }}%) &middot; {% if cand.days_rest is not none %}{{ cand.days_rest }}d rest{% else %}rest unknown{% endif %}{% if cand.rest_eligibility != 'available' and cand.preferred_rest %} (prefers {{ cand.preferred_rest }}){% endif %}</div>
  <div class="starter-card-reasoning">{{ cand.reasoning | e }}</div>
  {# ... existing recent_starts mini-log table, unchanged ... #}
</div>
```

Unavailable sub-block (render only when non-empty):

```jinja
{% if starter_prediction.unavailable_arms %}
<div class="starter-unavailable">
  <span class="starter-unavailable-label">Unavailable today</span>
  {% for arm in starter_prediction.unavailable_arms %}
  <div>&bull; {{ arm.name | e }} — {{ arm.reason | e }}</div>
  {% endfor %}
</div>
{% endif %}
```

> Field names above (`rest_eligibility`, `start_share_pct`, `preferred_rest`, `days_rest`, `throws`,
> `is_estimate`, `unavailable_arms`) follow the identifiers agreed in E-243-01/-02/-03. If the engine implementer
> chooses different attribute names, keep this spec and the template in sync — the rendered copy and layout are the
> contract, not the attribute spelling.

---

## Cross-references

- AC mapping: §1→AC-1/AC-4, §2→AC-2, §3→AC-3, §4→AC-5, §5→AC-6, "render unchanged" →AC-7, tests →AC-8/AC-9.
- Upstream: consumes E-243-01 rest-state (`rest_eligibility`/`preferred_rest`/`days_rest`) and E-243-02
  `is_estimate`.
- Deferred: per-arm estimate marker → IDEA-083 (epic TN-5 records the "no per-arm marker" ruling).
