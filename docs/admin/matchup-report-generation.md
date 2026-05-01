# Matchup Report Generation -- Operator Guide

*Last updated: 2026-04-30 | Source: E-228*

---

## What This Page Covers

This is the operator-facing guide for generating standalone scouting reports that include the **Game Plan** (matchup strategy) section. It documents every operator-touchable surface: feature flag, admin form, CLI flag, environment variables, and error/warning handling.

For the coach-facing description of what the Game Plan section *contains* and how to *read it*, see [Game Plan Section](../coaching/matchup-report.md).

---

## Feature Flag

The matchup feature is gated by an environment variable:

```
FEATURE_MATCHUP_ANALYSIS=1
```

**Recognised truthy values** (case-insensitive): `1`, `true`, `yes`. Anything else (unset, `0`, `false`, `no`, `off`, `anything-else`) means the feature is off.

When the flag is **off**:

- The admin form's matchup checkbox is hidden.
- The CLI accepts `--our-team` but emits a warning and ignores the value.
- `generate_report(...)` silently treats `our_team_id=...` as `None`. The report row is persisted with `our_team_id IS NULL`. The generated report renders without the Game Plan section.

This is the deliberate "kill switch" -- flipping the flag off restores pre-E-228 standalone scouting report behavior with zero other config changes.

Set the variable in your `.env` (development) or compose-managed environment (production), then restart the app.

---

## Admin Form

When the flag is on, the standalone report generation form (`/admin/reports/new` or whichever route is configured) shows:

- **Standard fields**: GameChanger team URL or public_id (required).
- **Matchup checkbox**: "Include matchup analysis (Game Plan section)". When checked, a dropdown appears.
- **Our-team dropdown**: lists all teams in the database with `membership_type = 'member'` -- i.e., your owned teams (LSB Freshman, JV, Varsity, Reserve, etc.). Pick the team whose perspective should drive the matchup analysis (the "us" side).

Submit the form. The admin route enqueues report generation as a FastAPI **background task** and redirects you back to the reports list (`/admin/reports`) immediately with a "Report generation started" flash message -- it does **not** wait for the pipeline to finish. Pipeline runtime is typically a few minutes (scouting crawl + load + spray + plays + reconciliation + matchup + render).

To see the finished report:

1. After the redirect, the new report row appears in the reports list with status `generating`.
2. Refresh the page periodically; status flips to `ready` when the background task completes (and the URL becomes a working link). Status flips to `failed` if the pipeline raised before reaching the render step.
3. Click the report URL; the Game Plan section sits between the executive summary and the Predicted Starter card.

**If a report stays in `generating` for longer than expected** (hours, not minutes), the background task likely raised after the row was created but before the row could be updated to `failed`. Check the app logs for warnings or errors tagged with the report's `public_id`. Restarting the app does not resume in-flight background tasks -- a stuck `generating` row will remain stuck until you delete it from the admin UI and re-submit the form.

---

## CLI Flag

The `bb report generate` command accepts `--our-team` for the same purpose:

```bash
bb report generate <gc-url-or-public-id> --our-team <team-id-or-public-id>
```

**Acceptable values** for `--our-team`:

- A numeric `teams.id` (the integer primary key in the `teams` table).
- A `public_id` slug (e.g., `lsb-varsity-2026`).
- A numeric string -- treated as a `teams.id`.

The CLI resolves the value to an integer `teams.id` before invoking `generate_report()`. If the value cannot be resolved (e.g., no team matches the slug), the CLI emits a clear error and exits non-zero without generating the report.

**Examples**:

```bash
# Resolve by team id
bb report generate https://web.gc.team-manager/team/abc123 --our-team 7

# Resolve by public_id slug
bb report generate abc123 --our-team lsb-varsity-2026
```

When the feature flag is off but the user passes `--our-team`, the CLI prints:

```
Warning: --our-team specified but FEATURE_MATCHUP_ANALYSIS is not enabled.
The matchup section will not appear in the generated report.
```

The report still generates -- just without the Game Plan section.

---

## OPENROUTER_API_KEY -- LLM Enrichment

The Game Plan section's *prose* (intro, per-hitter cues, SB / first-inning / loss-recipe interpretation) comes from an LLM call. That call requires:

```
OPENROUTER_API_KEY=<key>
```

Optional model override:

```
OPENROUTER_MODEL=anthropic/claude-haiku-4-5-20251001  # default
```

### FEATURE_MATCHUP_STRICT -- Hallucination Guardrail Mode

```
FEATURE_MATCHUP_STRICT=1   # default: unset (graceful)
```

Controls how the wrapper handles a hallucinated `hitter_cues[i].player_id` -- one returned by the LLM that does not round-trip to the grounding table's top-3 hitter IDs.

- **Unset / falsy (default, "graceful")**: the offending `hitter_cues` entry is filtered, a `WARNING` is logged, and the rest of the response is preserved. The report renders successfully with the remaining valid cues.
- **Set truthy (`1`, `true`, `yes`)**: any hallucinated `player_id` raises `LLMError`; the orchestration block then degrades the report to deterministic-only (no Game Plan prose). Use for development or model evaluation when you want to surface drift loudly rather than silently filter.

Recognised truthy values are case-insensitive: `1`, `true`, `yes`. Production should leave this unset.

**When `OPENROUTER_API_KEY` is unset OR the LLM call fails**:

- The orchestration block in `generate_report()` catches the failure non-fatally and logs a `WARNING` (`Matchup LLM enrichment failed for public_id=...`).
- The renderer receives the bare deterministic engine output and renders the section with deterministic content only -- no prose intro, no per-hitter cues, no SB/first-inning/loss-recipe prose.
- The generated report is still returned successfully -- coaches see the section with deterministic content.

This is the **degrade-by-hiding** pattern: LLM-prose surfaces hide on failure; deterministic surfaces (hitter names + PA badges + raw stats, SB counts, first-inning rates, loss-recipe bucket counts, pull-tendency notes, italic gray data notes) render unchanged.

---

## Suppress Behavior

When the engine determines the opponent has insufficient data to support any analysis (specifically: zero opposing top hitters AND zero opposing losses), it returns `confidence == "suppress"`. The orchestration block treats this as "no Game Plan section":

- The renderer is passed `matchup_data = None`.
- The rendered HTML contains **no trace** of the Game Plan section -- no header, no placeholder div, nothing.
- The Predicted Starter card renders in its normal post-exec-summary position.

This is intentional: pushing a section that says "insufficient data" wastes coach attention. If you see no Game Plan section in a report you expected to have one, check the opponent's data with `bb data status` or query the database directly -- they probably have no scouting load yet.

---

## Pipeline Sequencing

The matchup pipeline runs **after** plays/reconciliation. This is load-bearing: reconciliation can correct pitcher-attribution boundaries that the matchup engine relies on (for example, the loss-recipe bucket logic reads `player_game_pitching` rows, which reconciliation may correct).

Don't refactor the orchestration to run matchup earlier without reading the engine code -- the order is intentional.

### First-Inning Tendency Denominator

The First-Inning Tendency sub-section (`Scored in 1st: X of Y`, `Allowed in 1st: X of Y`) reports `Y` as the count of games **with plays loaded**, not every completed game on the schedule. When the plays stage fails or is incomplete for some games, those games are treated as "unknown" and excluded from the denominator -- not "0 of N" with the bug-prone implication that no first-inning runs occurred. If `Y` looks lower than the team's total game count, that's the plays-loaded count surfacing -- check `bb data status` or the plays-stage log for unloaded games.

---

## Generation Flow Summary

When you run `bb report generate <url> --our-team N` with the flag on and the LLM key set, the following happens (in order):

1. **Parse URL** → resolve public_id.
2. **Fetch public team info** → extract name, season year.
3. **Ensure team row** → upsert into `teams`.
4. **Create reports row** with status `generating` and `our_team_id = N`.
5. **Scouting crawl + load** → in-memory pipeline; populates games, rosters, season aggregates.
6. **Spray crawl + load** → adds spray events.
7. **Plays crawl + load + reconciliation** → adds pitch-by-pitch + corrects pitcher attribution.
8. **Matchup orchestration** (this story's contribution):
   - `build_matchup_inputs(conn, opponent_team_id, our_team_id, season_id, reference_date)` builds the input bundle.
   - `compute_matchup(inputs)` produces a deterministic `MatchupAnalysis`.
   - When `confidence != "suppress"` and `OPENROUTER_API_KEY` is set, `enrich_matchup(analysis, inputs)` adds LLM-authored prose (non-fatal).
9. **Render HTML** → `render_report(data)` writes the file under `data/reports/<slug>.html`.
10. **Mark report row `ready`** with the path.

If any step in 1-7 fails fatally, the report row is marked `failed` and the URL is returned with `success=False`. If step 8 fails, it logs a warning and proceeds without the Game Plan section -- the report still completes.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Game Plan section is missing entirely | Feature flag off OR `our_team_id` was None OR engine returned `suppress` | Check `FEATURE_MATCHUP_ANALYSIS` env var; verify form submission included team selection; check opponent has scouting data loaded |
| Game Plan section renders but has no prose intro / cues / interpretation | `OPENROUTER_API_KEY` unset OR LLM call failed | Check env var is set; check app logs for "Matchup LLM enrichment failed" WARNING |
| `--our-team` flag rejected with "could not resolve" | The provided id or slug doesn't match any team | Run `bb data status` to list teams; verify spelling of the public_id |
| Generated report fails entirely | Pipeline error before render -- not matchup-related | Check `bb data status` and app logs |

Logs to watch (in order of likelihood):

- `WARNING: FEATURE_MATCHUP_ANALYSIS disabled -- ignoring our_team_id=N` -- flag was off.
- `WARNING: Matchup LLM enrichment failed for public_id=X` -- LLM call failed; non-fatal, report continues.
- `WARNING: Matchup orchestration failed for public_id=X` -- something earlier in the orchestration block raised; non-fatal.

---

## Related Operator Pages

- [Operations](operations.md) -- top-level deployment + maintenance guide.
- [Standalone Reports](../coaching/standalone-reports.md) -- coach-facing description of the report.
- [Game Plan Section](../coaching/matchup-report.md) -- coach-facing description of the matchup section content.
