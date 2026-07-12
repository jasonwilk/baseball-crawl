"""THROWAWAY narrative model bake-off harness (research, read-only on src/+DB).

Feeds E-243-04 (re-point the Tier-2 LLM narration). Runs baseball-coach's
FINALIZED reframed probable-starter prompt across ~13 OpenRouter models on real,
intended-post-epic scenarios, scores every narrative with an LLM judge against
the coach's 7-criterion rubric, and emits a leaderboard + before/after pairs.

What it does NOT do:
  - modify any src/ code or DB rows (read-only: get_pitching_history etc.)

Intended-post-epic shape baked into each scenario (mirrors E-243-01/-02/-03):
  - the HARD rest-discount re-rank applied on top of the engine's ranking
    (reuses rerank_hard / rest_state from starter_backtest_rerank.py)
  - each ranked arm carries days_rest + rest-eligibility + last-outing facts
  - an unavailable_arms list (name + reason + days_short) from the engine gate
  - is_estimate=True for the youth/travel case (Pitch Smart soft prior)

Modes:
    --build-scenarios   construct + print the scenarios (no API calls)
    --list-models       fetch the live catalog + print the chosen slugs
    --smoke             run the first 2 chosen models (NEW prompt) only
    --full              full grid (NEW) + OLD-prompt baseline + LLM judge
  (default: --build-scenarios then --list-models, no spend)

Run: python3 .project/research/narrative_bakeoff.py --full
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RESEARCH_DIR))

from src.api.db import (  # noqa: E402
    get_pitching_history,
    build_pitcher_profiles,
)
from src.reports.starter_prediction import (  # noqa: E402
    compute_starter_prediction,
    detect_league_level,
    get_rules_for_league,
    get_nsaa_rules,
    format_nsaa_rest_table,
    _is_excluded,
)
# OLD prompt path (for the before/after baseline) -- imported verbatim so the
# baseline is the REAL current Tier-2 prompt, not a paraphrase.
from src.reports.llm_analysis import (  # noqa: E402
    _SYSTEM_PROMPT_TEMPLATE as OLD_SYSTEM_PROMPT_TEMPLATE,
    _build_user_prompt as old_build_user_prompt,
)
from src.llm.json_extract import extract_json_object  # noqa: E402
from src.llm.openrouter import LLMError  # noqa: E402

# Reuse the validated re-rank semantics from the sibling spike.
from starter_backtest_rerank import rest_state, rerank_hard  # noqa: E402

DB = str(ROOT / "data" / "app.db")
OUT_DIR = RESEARCH_DIR / "narrative-bakeoff"

_MODELS_URL = "https://openrouter.ai/api/v1/models"
_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 90

# Pitches-per-inning proxy when a real pitch count is unavailable (IP only).
_PITCHES_PER_INNING = 15

# Judge model -- a strong frontier model. Non-Anthropic to limit (not remove)
# same-vendor self-preference toward the Anthropic entrants in the field.
JUDGE_MODEL = "openai/gpt-5.1"

TEAMS = [
    (147, "2026", "<OWN-PROGRAM-REDACTED> Freshman"),
    (160, "2026", "<OWN-PROGRAM-REDACTED> Varsity"),
    (185, "2026", "<CITY-REDACTED> Post 216 Reserve"),
    (126, "2026", "Grand Island Home Federal Bank 18U"),
    (202, "2026", "Griffs Post 216 Juniors"),
    (91, "2026", "PrimeTime Westview Reserve"),
    (227, "2024", "Cornhusker LSW JV 2024"),
    (215, "2026", "Cornhusker LSW 2026"),
    (279, "2026", "Jr Bluejays 15U"),
    (189, "2026", "Gene's Auto Papio Post 32 Reserves"),
    (290, "2026", "<CITY-REDACTED> Post 216 Seniors"),
    (3, "2026", "<ORG-REDACTED> Repair Juniors"),
    (128, "2026", "<CITY-REDACTED> Hotel Group 18U"),
    (100, "2026", "<CITY-REDACTED> East Reserve 15U"),
    (336, "2026", "Nebraska Prospect 29s 15U"),
    (114, "2026", "<ORG-REDACTED> Solutions"),
    (186, "2026", "<TEAM-REDACTED> Construction"),
]


# ── Env / credentials ────────────────────────────────────────────────────


def load_api_key() -> str:
    """Load OPENROUTER_API_KEY from .env (read via dotenv, not exported)."""
    values = dotenv_values(str(ROOT / ".env"))
    key = values.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY missing from .env")
    return key


# ── Outing facts (shared by ranked + unavailable arms) ────────────────────


def _outing_facts(profile: dict, ref_date: datetime.date,
                  rules: Any) -> dict[str, Any] | None:
    """Most-recent-day facts: days_since, pitches (or None), ip_outs, required
    rest, days_short. Pitch/ip aggregation matches ``_is_excluded`` (sum over
    the most recent game day -- doubleheaders included)."""
    apps = profile.get("appearances", [])
    if not apps:
        return None
    last_date_str = apps[-1].get("game_date")
    if not last_date_str:
        return None
    try:
        last_date = datetime.date.fromisoformat(last_date_str)
    except (ValueError, TypeError):
        return None
    days_since = (ref_date - last_date).days
    last_day = [a for a in apps if a.get("game_date") == last_date_str]
    pcounts = [a.get("pitches") for a in last_day]
    pitches = None if any(p is None for p in pcounts) else sum(pcounts)
    ip_outs = sum(a.get("ip_outs") or 0 for a in last_day)

    required = 0
    if pitches is not None and rules is not None:
        for tier in rules.rest_tiers:
            if tier.min_pitches <= pitches <= tier.max_pitches:
                required = tier.rest_days
                break
        else:
            if (pitches > 0 and rules.rest_tiers
                    and pitches > rules.rest_tiers[-1].max_pitches):
                required = rules.rest_tiers[-1].rest_days
    days_short = max(required - days_since, 0)
    return {
        "days_since": days_since,
        "pitches": pitches,
        "ip_outs": ip_outs,
        "required_rest": required,
        "days_short": days_short,
    }


def _format_ip(ip_outs: int) -> str:
    """Standard baseball IP notation: X.Y where Y is outs 0-2 (NOT decimal).
    19 outs -> "6.1" (6 innings + 1 out), not 6.33. Coach-flagged bug fix."""
    innings, outs = divmod(int(ip_outs or 0), 3)
    return f"{innings}.{outs}"


def _pitch_display(pitches: int | None, ip_outs: int) -> str:
    """Coach's pitch_display translation: real count, else IP-proxy estimate."""
    if pitches is not None:
        return f"{pitches} pitches"
    if ip_outs:
        est = round((ip_outs / 3) * _PITCHES_PER_INNING)
        return f"estimated {est}+ pitches (from {_format_ip(ip_outs)} IP)"
    return "an unknown pitch count"


def _availability_label(eligibility: str) -> str:
    return ("fully rested" if eligibility == "available"
            else "eligible but on short rest")


def _derive_rank_context(rotation_pattern: str, idx: int, games_started: int,
                         max_gs: int) -> str | None:
    """Clean rotation-slot label computed on the POST-rerank order (so a
    promoted fresh arm gets the right label, unlike the engine's reasoning
    string which is baked pre-rerank). Mirrors the engine's rank_context
    vocabulary in ``compute_starter_prediction``."""
    if rotation_pattern == "ace-dominant":
        if idx == 0:
            return "Ace starter" if games_started == max_gs \
                else "Next available starter"
        return None
    if rotation_pattern == "2-man rotation":
        return "Next in 2-man rotation"
    if rotation_pattern == "3-man rotation":
        return "Next in 3-man rotation"
    if rotation_pattern == "committee":
        return "Committee candidate"
    return None


# ── Scenario construction ────────────────────────────────────────────────


@dataclass
class Arm:
    name: str
    jersey_number: int | None
    games_started: int
    start_share: float
    days_rest: int | None
    last_outing_pitches: int | None
    ip_outs_last: int
    eligibility: str            # "available" | "discounted"
    likelihood: float
    reasoning: str              # verbatim engine _build_reasoning string
    rank_context: str | None    # clean post-rerank rotation-slot label (B)


@dataclass
class Scenario:
    key: str
    team_id: int
    season_id: str
    label: str
    game_date: str
    league: str
    is_estimate: bool
    rotation_pattern: str
    confidence: str
    total_team_games: int
    team_record: str | None
    ranked_arms: list[Arm] = field(default_factory=list)
    unavailable_arms: list[dict[str, Any]] = field(default_factory=list)
    data_note: str | None = None


def _ordered_games(history: list[dict]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    order: list[tuple[str, str]] = []
    for r in history:
        gid = r["game_id"]
        if gid not in seen:
            seen.add(gid)
            order.append((gid, r["game_date"]))
    return order


def _team_record_asof(conn, team_id: int, season_id: str,
                      asof_date: str) -> str | None:
    try:
        rows = conn.execute(
            """
            SELECT home_team_id, away_team_id, home_score, away_score
            FROM games
            WHERE status = 'completed' AND game_date < ?
              AND (home_team_id = ? OR away_team_id = ?)
            """,
            (asof_date, team_id, team_id),
        ).fetchall()
    except Exception:  # noqa: BLE001
        return None
    wins = losses = 0
    for home_id, away_id, hs, as_ in rows:
        if hs is None or as_ is None:
            continue
        us, them = (hs, as_) if home_id == team_id else (as_, hs)
        if us > them:
            wins += 1
        elif us < them:
            losses += 1
    return f"{wins}-{losses}" if (wins or losses) else None


def _enrich(conn, team_id, season_id, label, gdate, league,
            is_estimate) -> Scenario | None:
    history = get_pitching_history(team_id, season_id, db=conn)
    asof = [r for r in history if r["game_date"] < gdate]
    if not asof:
        return None
    ref_date = datetime.date.fromisoformat(gdate)
    profiles = build_pitcher_profiles(asof)
    pred = compute_starter_prediction(
        profiles, asof, reference_date=ref_date, workload=None, league=league,
    )
    if not pred.top_candidates:
        return None

    reordered_ids = rerank_hard(pred.top_candidates, profiles, ref_date)
    by_id = {c["player_id"]: c for c in pred.top_candidates}
    ranked = [by_id[pid] for pid in reordered_ids]
    total_games = len({r["game_id"] for r in asof})
    rules = get_rules_for_league(league, ref_date)
    max_gs = max((p["total_starts"] for p in profiles.values()), default=0)

    arms: list[Arm] = []
    for idx, c in enumerate(ranked):
        pid = c["player_id"]
        days_rest, last_pitches, _pref, discounted = rest_state(
            profiles[pid], ref_date
        )
        facts = _outing_facts(profiles[pid], ref_date, rules) or {}
        arms.append(Arm(
            name=c["name"],
            jersey_number=c.get("jersey_number"),
            games_started=c["games_started"],
            start_share=round(c["games_started"] / total_games, 3)
            if total_games else 0.0,
            days_rest=days_rest,
            last_outing_pitches=last_pitches,
            ip_outs_last=facts.get("ip_outs", 0),
            eligibility="discounted" if discounted else "available",
            likelihood=c["likelihood"],
            reasoning=c["reasoning"],
            rank_context=_derive_rank_context(
                pred.rotation_pattern, idx, c["games_started"], max_gs),
        ))

    unavailable: list[dict[str, Any]] = []
    if rules is not None:
        for pid, p in profiles.items():
            excl, reason = _is_excluded(p, ref_date, rules)
            if excl:
                facts = _outing_facts(p, ref_date, rules) or {}
                unavailable.append({
                    "name": f"{p['first_name']} {p['last_name']}",
                    "jersey_number": p.get("jersey_number"),
                    "reason": reason,
                    "days_since": facts.get("days_since"),
                    "pitches": facts.get("pitches"),
                    "ip_outs": facts.get("ip_outs", 0),
                    "days_short": facts.get("days_short"),
                })

    return Scenario(
        key="", team_id=team_id, season_id=season_id, label=label,
        game_date=gdate, league=league, is_estimate=is_estimate,
        rotation_pattern=pred.rotation_pattern, confidence=pred.confidence,
        total_team_games=total_games,
        team_record=_team_record_asof(conn, team_id, season_id, gdate),
        ranked_arms=arms, unavailable_arms=unavailable,
        data_note=pred.data_note,
    )


def _classify(scn: Scenario) -> str | None:
    arms = scn.ranked_arms
    if not arms:
        return None
    if (arms[0].eligibility == "available"
            and any(a.eligibility == "discounted" for a in arms[1:])):
        if any(a.eligibility == "discounted" and a.likelihood >= arms[0].likelihood
               for a in arms[1:]):
            return "tired_arm"
    if scn.rotation_pattern in ("2-man rotation", "ace-dominant"):
        return "clear_rotation"
    if scn.rotation_pattern == "committee" and len(arms) >= 3:
        return "committee"
    if scn.total_team_games <= 5:
        return "low_data"
    return None


def _tired_arm_quality(scn: Scenario) -> int:
    top = scn.ranked_arms[0]
    score = 0
    if top.games_started >= 2:
        score += 2
    if top.days_rest is not None and top.days_rest < 10:
        score += 1
    return score


def build_scenarios(conn) -> list[Scenario]:
    scan_buckets = ["tired_arm", "committee", "clear_rotation", "low_data"]
    candidates: dict[str, list[Scenario]] = {b: [] for b in scan_buckets}

    for team_id, season_id, label in TEAMS:
        league = detect_league_level(team_name=label)
        forced = "legion" if league == "youth_travel" else "nsaa_varsity"
        history = get_pitching_history(team_id, season_id, db=conn)
        order = _ordered_games(history)
        seen_buckets: set[str] = set()
        for i, (_gid, gdate) in enumerate(order):
            if i < 4:
                continue
            scn = _enrich(conn, team_id, season_id, label, gdate, forced,
                          is_estimate=False)
            if scn is None:
                continue
            bucket = _classify(scn)
            if bucket in scan_buckets and bucket not in seen_buckets:
                scn.key = bucket
                candidates[bucket].append(scn)
                seen_buckets.add(bucket)

    candidates["tired_arm"].sort(key=_tired_arm_quality, reverse=True)

    found: dict[str, Scenario] = {}
    used_teams: set[int] = set()
    for bucket in ["tired_arm", "clear_rotation", "committee", "low_data"]:
        pool = candidates[bucket]
        pick = next((s for s in pool if s.team_id not in used_teams), None)
        if pick is None and pool:
            pick = pool[0]
        if pick is not None:
            found[bucket] = pick
            used_teams.add(pick.team_id)

    youth_teams = [t for t in TEAMS
                   if detect_league_level(team_name=t[2]) == "youth_travel"]
    youth_teams.sort(key=lambda t: t[0] in used_teams)
    for team_id, season_id, label in youth_teams:
        history = get_pitching_history(team_id, season_id, db=conn)
        order = _ordered_games(history)
        for _gid, gdate in reversed(order):
            scn = _enrich(conn, team_id, season_id, label, gdate, "legion",
                          is_estimate=True)
            if scn is not None and scn.ranked_arms:
                scn.key = "youth_estimate"
                found["youth_estimate"] = scn
                break
        if "youth_estimate" in found:
            break

    ordered_keys = ["committee", "tired_arm", "youth_estimate",
                    "clear_rotation", "low_data"]
    return [found[k] for k in ordered_keys if k in found]


def coach_example_scenario() -> Scenario:
    """baseball-coach's verbatim Variant-B EXAMPLE as a synthetic scenario.

    WHY THIS EXISTS: a scan of all 17 loaded teams found ZERO real cases where
    the engine emits a DIFFERENTIATED rotation Role that explains a more-rested
    arm ranked below a less-rested #1 (the engine classifies these as
    "committee", so every arm's rank_context is the uniform "Committee
    candidate"). B's whole rotation-rationale lever therefore cannot fire on
    real data. This synthetic case injects coach's exact example (differentiated
    Roles, #1 Draus 7d ranked over #2 Hirschbrunner 8d) so B's mechanism is
    testable in the one condition it was designed for. Clearly labelled as
    synthetic in the report.
    """
    arms = [
        Arm("Ian Draus", 12, 2, round(2 / 8, 3), 7, 105, 19, "available",
            0.60, "Next in rotation", "Next in 2-man rotation"),
        Arm("Zach Hirschbrunner", 9, 2, round(2 / 8, 3), 8, 57, 12, "available",
            0.30, "Next available", "Next available starter"),
        Arm("Jaxon Pieper", 4, 1, round(1 / 8, 3), 3, 90, 13, "discounted",
            0.20, "Short rest", "Committee candidate"),
    ]
    return Scenario(
        key="rotation_role_synthetic", team_id=-1, season_id="synthetic",
        label="Coach Example (synthetic rotation case)",
        game_date="2024-06-05", league="nsaa_varsity", is_estimate=False,
        rotation_pattern="2-man rotation", confidence="moderate",
        total_team_games=8, team_record="8-4", ranked_arms=arms,
        unavailable_arms=[{
            "name": "Nicolas Luciani", "jersey_number": 7, "reason":
            "1d rest -- needs 2", "days_since": 1, "pitches": 63,
            "ip_outs": 0, "days_short": 1,
        }],
        data_note=None,
    )


# ── NEW prompt (baseball-coach finalized, verbatim) ───────────────────────


NEW_SYSTEM_PROMPT = """\
You are a baseball scout writing a brief bench briefing for a high school coach \
preparing for today's game. The ranked pitching data has already been computed \
for you — your job is to narrate it in 2-4 sentences of plain English prose.

STRUCTURE (follow this order):
1. Lead with the single most-likely arm by name and the concrete reason — how \
many days of rest they have, or how many pitches they threw and when. One \
name. One reason. First sentence.
2. Mention the next 1-2 likely arms if they appear in the data, with their \
rest situation.
3. Name anyone who is unavailable today and state why in plain English (e.g., \
"threw 72 pitches four days ago and needs one more day").
4. If the data is flagged as a pitch-count estimate, say so plainly in one \
phrase (e.g., "rest eligibility is estimated — their league rules aren't on \
file").

HARD RULES:
— Always name a specific pitcher in your first sentence. Never open with \
uncertainty, ambiguity, or a description of the situation.
— The ranked order in the data is correct. Do not reorder, reverse, or qualify \
the ranking. Do not present the #2 arm as more likely than #1.
— 2-4 sentences total. No bullet lists. Flowing prose only.
— Never use these words or phrases: "committee situation," "committee," "Pitch \
Smart," "Legion," "WHIP," "FIP," or any phrase that amounts to refusing to \
name a likely starter.
— "Days of rest" and "threw X pitches N days ago" are fine. Rule-set names and \
advanced stats are not.
— A discounted arm (eligible but on short rest) is still a real candidate — \
mention it, but as secondary to a fully-rested arm.
"""

# Variant A = the validated prompt above (alias for clarity in --ab).
A_SYSTEM_PROMPT = NEW_SYSTEM_PROMPT

# Variant B = baseball-coach's ENHANCED prompt (verbatim). Adds Role-based
# rotation rationale + committee-honesty handling, drops IP from the data block.
B_PROMPT_READY = True
B_SYSTEM_PROMPT = """\
You are a baseball scout writing a brief bench briefing for a high school coach \
preparing for today's game. The ranked pitching data has already been computed \
for you — your job is to narrate it in 2-4 sentences of plain English prose.

STRUCTURE (follow this order):
1. Lead with the most-likely arm by name. Give the REASON it is ranked first:
   - If rest clearly explains the ranking (the #1 arm has more rest than the \
others), citing the rest gap is enough.
   - If the #1 arm has LESS rest than a lower-ranked fully-available arm, use \
the Role field to explain the ranking — say "next in their rotation," "their \
most-used starter," or "their ace." Never leave a coach wondering why a \
more-rested arm is ranked lower.
   - If all arms show Role: "Committee candidate," there is no rotation-slot \
reason — acknowledge that honestly (e.g., "Caspar and Nelson both have seven \
days of rest and are equally likely starters") rather than inventing a \
rotation story.
2. Mention the next 1-2 likely arms with their rest situation and, where \
useful, their role.
3. Name anyone unavailable today and state why in plain English.
4. If the data is flagged as a pitch-count estimate, say so plainly (e.g., \
"rest eligibility is estimated — their league rules aren't on file").

HARD RULES:
— Always name a specific pitcher in your first sentence. Never open with \
uncertainty or hedging.
— The ranked order in the data is correct. Do not reorder, reverse, or qualify \
the ranking.
— 2-4 sentences total. No bullet lists. Flowing prose only.
— Never use: "committee situation," "committee," "Pitch Smart," "Legion," \
"WHIP," "FIP," or any phrase that amounts to refusing to name a likely starter.
— "Days of rest," "threw X pitches N days ago," "next in their rotation," \
"their most-used starter," "their ace" are all fine. Rule-set names and \
advanced stats are not.

EXAMPLE — how to handle a rotation-order case:

Input data:
1. Ian Draus — 7 days rest, fully rested | 105 pitches 7 days ago | Starts: 2 \
of 8 | Role: Next in 2-man rotation
2. Zach Hirschbrunner — 8 days rest, fully rested | 57 pitches 8 days ago | \
Starts: 2 of 8 | Role: Next available starter
3. Jaxon Pieper — 3 days rest, eligible but on short rest | 90 pitches 3 days \
ago | Starts: 1 of 8 | Role: Committee candidate
Unavailable: Nicolas Luciani — 63 pitches 1 day ago, needs 1 more day

Ideal output:
"Ian Draus is your most likely arm today — next in their rotation after seven \
days of rest from a 105-pitch start. Zach Hirschbrunner is the next option on \
eight days, fully rested from a lighter 57-pitch outing. Jaxon Pieper is \
eligible but on short rest after 90 pitches three days ago, so expect him in \
relief if needed. Nicolas Luciani threw 63 pitches yesterday and needs one \
more day."
"""

# Temperature for the A/B run. Coach: 0.0 for both variants (lowest supported).
AB_TEMPERATURE = 0.0


def build_new_user_prompt(scn: Scenario, *,
                          include_rationale: bool = False) -> str:
    """Coach USER/DATA BLOCK template with the field translations.

    Shared by variant A (include_rationale=False) and variant B
    (include_rationale=True appends the engine rotation-rationale per arm).
    IP renders in standard baseball notation (X.Y) per the coach IP fix.
    """
    lines: list[str] = [f"OPPONENT: {scn.label}", "", "MOST LIKELY ARMS TODAY:"]
    only_one = len(scn.ranked_arms) == 1
    for idx, a in enumerate(scn.ranked_arms, 1):
        jersey = a.jersey_number if a.jersey_number is not None else "?"
        label = _availability_label(a.eligibility)
        if only_one and idx == 1:
            label += " (only eligible arm today)"
        pitch = _pitch_display(a.last_outing_pitches, a.ip_outs_last)
        days_since = a.days_rest if a.days_rest is not None else "?"
        line = (
            f"{idx}. {a.name} (#{jersey}) — {days_since} days rest, {label} | "
            f"{pitch} {days_since} days ago ({_format_ip(a.ip_outs_last)} IP) | "
            f"{a.games_started} of {scn.total_team_games} starts this season"
        )
        if include_rationale:
            # B-only: surface the rotation-slot rationale. Coach will confirm
            # whether B consumes rank_context (clean slot label) or the full
            # engine reasoning string; both are carried so we can flip cheaply.
            rationale = a.rank_context or a.reasoning
            if rationale:
                line += f" | rotation note: {rationale}"
        lines.append(line)

    if scn.unavailable_arms:
        lines.append("")
        lines.append("UNAVAILABLE TODAY:")
        for u in scn.unavailable_arms:
            pitch = _pitch_display(u.get("pitches"), u.get("ip_outs", 0))
            ds = u.get("days_since")
            ds_str = ds if ds is not None else "?"
            short = u.get("days_short") or 1
            lines.append(
                f"- {u['name']}: {pitch} {ds_str} days ago — needs {short} "
                f"more day(s) of rest before eligible"
            )

    if scn.is_estimate:
        lines.append("")
        lines.append(
            "NOTE: This opponent's league pitch rules are not on file. The "
            "rest eligibility above is a standard pitch-count estimate — the "
            "actual rules may differ, so treat borderline calls as approximate."
        )

    lines.append("")
    lines.append("Write a 2-4 sentence briefing for the coach now.")
    return "\n".join(lines)


def _b_pitch_display(pitches: int | None, ip_outs: int) -> str:
    """Variant B pitch_display: real count only; IP-proxy/null -> proxy note
    with NO IP shown (coach dropped IP from B's data block)."""
    if pitches is not None:
        return f"{pitches} pitches"
    if ip_outs:
        est = round((ip_outs / 3) * _PITCHES_PER_INNING)
        return f"estimated {est}+ pitches (proxy)"
    return "an unknown pitch count"


def build_b_user_prompt(scn: Scenario) -> str:
    """baseball-coach's Variant B USER/DATA BLOCK (verbatim): adds a Role field
    (rank_context, verbatim), drops IP entirely, real pitch count only."""
    lines: list[str] = [f"OPPONENT: {scn.label}", "", "MOST LIKELY ARMS TODAY:"]
    only_one = len(scn.ranked_arms) == 1
    for idx, a in enumerate(scn.ranked_arms, 1):
        jersey = a.jersey_number if a.jersey_number is not None else "?"
        label = _availability_label(a.eligibility)
        if only_one and idx == 1:
            label += " (only eligible arm today)"
        pitch = _b_pitch_display(a.last_outing_pitches, a.ip_outs_last)
        days_since = a.days_rest if a.days_rest is not None else "?"
        role = a.rank_context or "Committee candidate"
        lines.append(
            f"{idx}. {a.name} (#{jersey}) — {days_since} days rest, {label} | "
            f"{pitch} {days_since} days ago | "
            f"Starts: {a.games_started} of {scn.total_team_games} | Role: {role}"
        )

    if scn.unavailable_arms:
        lines.append("")
        lines.append("UNAVAILABLE TODAY:")
        for u in scn.unavailable_arms:
            pitch = _b_pitch_display(u.get("pitches"), u.get("ip_outs", 0))
            ds = u.get("days_since")
            ds_str = ds if ds is not None else "?"
            short = u.get("days_short") or 1
            lines.append(
                f"- {u['name']}: {pitch} {ds_str} days ago — needs {short} "
                f"more day(s) before eligible"
            )

    if scn.is_estimate:
        lines.append("")
        lines.append(
            "NOTE: This opponent's league pitch rules are not on file. Rest "
            "eligibility is a standard pitch-count estimate — treat borderline "
            "calls as approximate."
        )

    lines.append("")
    lines.append("Write a 2-4 sentence briefing for the coach now.")
    return "\n".join(lines)


# ── OLD prompt (current Tier-2, for before/after) ─────────────────────────


def build_old_messages(scn: Scenario, conn) -> list[dict[str, str]]:
    """Reconstruct the REAL current Tier-2 messages for the before/after."""
    history = get_pitching_history(scn.team_id, scn.season_id, db=conn)
    asof = [r for r in history if r["game_date"] < scn.game_date]
    ref_date = datetime.date.fromisoformat(scn.game_date)
    profiles = build_pitcher_profiles(asof)
    pred = compute_starter_prediction(
        profiles, asof, reference_date=ref_date, workload=None,
        league=scn.league,
    )
    system = OLD_SYSTEM_PROMPT_TEMPLATE.format(
        nsaa_rest_table=format_nsaa_rest_table(get_nsaa_rules(ref_date)),
    )
    user = old_build_user_prompt(pred, asof, team_record=scn.team_record)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# ── Model selection ──────────────────────────────────────────────────────


PREFERRED_SLUGS = [
    "anthropic/claude-opus-4.8",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-5.1",
    "openai/gpt-5-mini",
    "google/gemini-3.1-pro-preview",
    "google/gemini-3.5-flash",
    "google/gemini-2.5-flash-lite",
    "x-ai/grok-4.3",
    "meta-llama/llama-4-maverick",
    "mistralai/mistral-large-2512",
    "deepseek/deepseek-v3.2",
    "qwen/qwen3-max",
]


def fetch_catalog(api_key: str) -> dict[str, dict[str, Any]]:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(_MODELS_URL,
                          headers={"Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
    return {m["id"]: m for m in resp.json().get("data", [])}


def select_models(catalog) -> tuple[list[str], list[str]]:
    chosen = [s for s in PREFERRED_SLUGS if s in catalog]
    missing = [s for s in PREFERRED_SLUGS if s not in catalog]
    return chosen, missing


def price_of(catalog, slug) -> tuple[float, float]:
    pricing = catalog.get(slug, {}).get("pricing", {}) or {}
    try:
        return (float(pricing.get("prompt", 0.0)),
                float(pricing.get("completion", 0.0)))
    except (TypeError, ValueError):
        return 0.0, 0.0


# ── Transport ─────────────────────────────────────────────────────────────


@dataclass
class RawCall:
    ok: bool
    content: str | None
    latency_s: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    error: str | None


def _post_chat(api_key, model, messages, catalog, *,
               response_format=None, max_tokens=1024,
               temperature=0.3) -> RawCall:
    """Low-level OpenRouter chat call. Never raises -- failures are recorded."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "usage": {"include": True},
    }
    if response_format is not None:
        body["response_format"] = response_format
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(_CHAT_URL, headers=headers, json=body)
    except httpx.HTTPError as exc:
        return RawCall(False, None, round(time.monotonic() - started, 2),
                       None, None, None, f"transport: {exc}")
    latency = round(time.monotonic() - started, 2)
    if resp.status_code >= 400:
        return RawCall(False, None, latency, None, None, None,
                       f"http {resp.status_code}: {resp.text[:160]}")
    try:
        payload = resp.json()
    except ValueError as exc:
        return RawCall(False, None, latency, None, None, None,
                       f"bad json envelope: {exc}")
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        return RawCall(False, None, latency, None, None, None,
                       f"no content: {exc}")
    usage = payload.get("usage") or {}
    pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
    cost = usage.get("cost")
    if cost is None and pt is not None and ct is not None:
        pp, cp = price_of(catalog, model)
        cost = pt * pp + ct * cp
    cost = round(float(cost), 6) if cost is not None else None
    return RawCall(True, content, latency, pt, ct, cost, None)


# ── Generation ─────────────────────────────────────────────────────────────


@dataclass
class CallResult:
    model: str
    scenario_key: str
    prompt_tag: str             # "new" | "old"
    ok: bool
    narrative: str | None
    raw_content: str | None
    latency_s: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    error: str | None
    scores: dict[str, int] | None = None
    judge_total: int | None = None
    judge_note: str | None = None


def generate(api_key, model, scn, catalog, *, prompt_tag, conn) -> CallResult:
    if prompt_tag in ("new", "A"):  # variant A (validated NEW prompt)
        messages = [
            {"role": "system", "content": A_SYSTEM_PROMPT},
            {"role": "user", "content": build_new_user_prompt(scn)},
        ]
        rc = _post_chat(api_key, model, messages, catalog,
                        temperature=AB_TEMPERATURE)  # prose, no JSON
        narrative = rc.content.strip() if rc.content else None
    elif prompt_tag == "B":  # variant B (coach's enhanced prompt + Role field)
        messages = [
            {"role": "system", "content": B_SYSTEM_PROMPT},
            {"role": "user", "content": build_b_user_prompt(scn)},
        ]
        rc = _post_chat(api_key, model, messages, catalog,
                        temperature=AB_TEMPERATURE)
        narrative = rc.content.strip() if rc.content else None
    else:  # old (current Tier-2 baseline)
        messages = build_old_messages(scn, conn)
        rc = _post_chat(api_key, model, messages, catalog,
                        response_format={"type": "json_object"})
        narrative = None
        if rc.content:
            try:
                narrative = extract_json_object(rc.content).get("narrative")
            except (LLMError, AttributeError):
                narrative = None
    return CallResult(
        model=model, scenario_key=scn.key, prompt_tag=prompt_tag, ok=rc.ok,
        narrative=narrative, raw_content=rc.content, latency_s=rc.latency_s,
        prompt_tokens=rc.prompt_tokens, completion_tokens=rc.completion_tokens,
        cost_usd=rc.cost_usd, error=rc.error,
    )


# ── LLM judge ──────────────────────────────────────────────────────────────


_RUBRIC = """\
Score a probable-starter bench briefing on 7 criteria. C1 and C2 are 0-3 (core \
failure modes); C3-C7 are 0-2. Max 16.
C1 Named arm + concrete reason (0-3): 3=first sentence names the top-ranked arm \
+ a specific reason (days rest OR pitch count w/ date); 0=no name in first \
sentence / opens with a hedge.
C2 Faithful to deterministic ranking (0-3): 3=correct order, a discounted arm \
framed as secondary, no invented arm; 0=contradicts ranking / names a pitcher \
not in the data / refuses to rank.
C3 Unavailable arms surfaced (0-2): 2=all named with a plain reason; 0=none \
mentioned despite a non-empty UNAVAILABLE list.
C4 No hedging / no committee cop-out (0-2): 2=commits to an order; 0=dominated \
by "committee"/"hard to predict"/"multiple arms could start".
C5 Plain English, no jargon, estimate flagged (0-2): 2=no Pitch Smart/Legion/\
WHIP/FIP/ERA AND the estimate caveat is present when the data is flagged as an \
estimate; 0=multiple jargon terms OR an estimate presented as confirmed.
C6 Rest/rotation reason specific (0-2): 2=uses the actual numbers; 0=no numbers \
despite data.
C7 Concise / bench-ready (0-2): 2=2-4 sentences, no padding; 0=under 2 or 7+ \
sentences.
Score each criterion INDEPENDENTLY before totaling; do not let overall \
impression anchor. A 0 on C1 or C2 flags the output regardless of total."""

# baseball-coach's two binary trust sub-checks (separate from the 16-pt rubric).
# Each is 0/1 and reported alongside but NOT folded into the rubric total.
# Applied per scenario by the report (rot -> rotation-order case; comm ->
# pure-committee case). The judge always returns both; -1 means N/A.
_SUBCHECKS = (
    "Also return two binary trust sub-checks (0 or 1, or -1 if not applicable "
    "to this scenario):\n"
    'ROT (rotation rationale): applies when the #1 arm has LESS rest than a '
    "lower-ranked fully-available arm. Score 1 if the narrative uses "
    "rotation/role language (e.g., 'next in their rotation', 'their most-used "
    "starter', 'their ace') to justify why the more-rested arm is ranked "
    "lower; 0 if it cites rest as if rest explains the ranking, or is "
    "ambiguous; -1 if the #1 arm is the most-rested (rest explains it, sub-"
    "check N/A).\n"
    'COMM (committee honesty): applies when ALL arms have Role "Committee '
    'candidate". Score 1 if the narrative acknowledges the top arms are '
    "roughly equally likely (honest about no clear rotation slot); 0 if it "
    "invents a rotation/role rationale that the data does not support; -1 if "
    "the arms are not all committee-role."
)

_JUDGE_SYSTEM = (
    "You are a strict evaluator of baseball scouting briefings. " + _RUBRIC +
    "\n\n" + _SUBCHECKS +
    "\n\nRespond ONLY with a JSON object: "
    '{"c1":int,"c2":int,"c3":int,"c4":int,"c5":int,"c6":int,"c7":int,'
    '"rot":int,"comm":int,"note":"<=15 word justification"}. '
    "Use the exact integer ranges above."
)


def _judge_data_block(scn: Scenario) -> str:
    """Ground-truth the judge needs to check faithfulness (C2/C3/C5)."""
    lines = [f"OPPONENT: {scn.label}",
             f"ESTIMATE_FLAG: {scn.is_estimate}",
             "RANKED ARMS (this exact order is correct):"]
    for i, a in enumerate(scn.ranked_arms, 1):
        lines.append(
            f"  {i}. {a.name} — {a.days_rest} days rest, {a.eligibility}, "
            f"{a.last_outing_pitches} pitches last outing, "
            f"{a.games_started}/{scn.total_team_games} starts, "
            f"Role: {a.rank_context or 'Committee candidate'}"
        )
    if scn.unavailable_arms:
        lines.append("UNAVAILABLE:")
        for u in scn.unavailable_arms:
            lines.append(f"  - {u['name']}: {u['reason']}")
    else:
        lines.append("UNAVAILABLE: (none)")
    return "\n".join(lines)


def judge(api_key, scn, narrative, catalog) -> tuple[dict | None, int | None,
                                                     str | None, float | None]:
    user = (_judge_data_block(scn) +
            "\n\nBRIEFING TO SCORE:\n" + (narrative or "(empty)"))
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": user},
    ]
    rc = _post_chat(api_key, JUDGE_MODEL, messages, catalog,
                    response_format={"type": "json_object"}, max_tokens=400)
    if not rc.ok or not rc.content:
        return None, None, f"judge failed: {rc.error}", rc.cost_usd
    try:
        parsed = extract_json_object(rc.content)
    except (LLMError, AttributeError) as exc:
        return None, None, f"judge unparsed: {exc}", rc.cost_usd
    scores: dict[str, int] = {}
    for k in ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]:
        try:
            scores[k] = int(parsed.get(k))
        except (TypeError, ValueError):
            scores[k] = 0
    total = sum(scores.values())  # max 16 -- sub-checks are NOT folded in
    for k in ("rot", "comm"):
        try:
            scores[k] = int(parsed.get(k))
        except (TypeError, ValueError):
            scores[k] = -1  # N/A / unparseable
    return scores, total, parsed.get("note"), rc.cost_usd


# ── Orchestration ──────────────────────────────────────────────────────────


def run_generation(api_key, models, scenarios, catalog, conn, *,
                   prompt_tag, pacing=1.0) -> list[CallResult]:
    results: list[CallResult] = []
    total = len(models) * len(scenarios)
    n = 0
    for model in models:
        for scn in scenarios:
            n += 1
            print(f"  [{prompt_tag} {n}/{total}] {model} x {scn.key} ...",
                  flush=True)
            res = generate(api_key, model, scn, catalog,
                           prompt_tag=prompt_tag, conn=conn)
            if not res.ok:
                print(f"      FAILED: {res.error}", flush=True)
            results.append(res)
            time.sleep(pacing)
    return results


def run_judge(api_key, results, scenarios, catalog) -> float:
    scn_by_key = {s.key: s for s in scenarios}
    judge_cost = 0.0
    for n, r in enumerate(results, 1):
        if not r.ok or not r.narrative:
            continue
        scn = scn_by_key.get(r.scenario_key)
        if scn is None:
            continue
        print(f"  [judge {n}/{len(results)}] {r.model} x {r.scenario_key} "
              f"({r.prompt_tag}) ...", flush=True)
        scores, total, note, cost = judge(api_key, scn, r.narrative, catalog)
        r.scores, r.judge_total, r.judge_note = scores, total, note
        if cost:
            judge_cost += cost
        time.sleep(0.7)
    return judge_cost


# ── Output / leaderboard ───────────────────────────────────────────────────


def _mean(xs: list[float]) -> float | None:
    return round(statistics.fmean(xs), 2) if xs else None


def build_leaderboard(results: list[CallResult]) -> list[dict[str, Any]]:
    """Per-model aggregates over the NEW-prompt outputs."""
    by_model: dict[str, list[CallResult]] = {}
    for r in results:
        if r.prompt_tag != "new":
            continue
        by_model.setdefault(r.model, []).append(r)

    rows: list[dict[str, Any]] = []
    for model, recs in by_model.items():
        scored = [r for r in recs if r.judge_total is not None]
        totals = [float(r.judge_total) for r in scored]
        crit_means = {}
        for c in ["c1", "c2", "c3", "c4", "c5", "c6", "c7"]:
            vals = [float(r.scores[c]) for r in scored if r.scores]
            crit_means[c] = _mean(vals)
        rows.append({
            "model": model,
            "n_scored": len(scored),
            "mean_total": _mean(totals),
            "crit_means": crit_means,
            "mean_latency_s": _mean([r.latency_s for r in recs
                                     if r.latency_s is not None]),
            # Costs are sub-cent: keep 6 decimals, not _mean's 2 (which would
            # collapse every cheap model to $0.00).
            "mean_cost_usd": (
                round(statistics.fmean([r.cost_usd for r in recs
                                        if r.cost_usd is not None]), 6)
                if any(r.cost_usd is not None for r in recs) else None),
            "failures": sum(1 for r in recs if not r.ok),
        })
    rows.sort(key=lambda x: (x["mean_total"] is not None,
                             x["mean_total"] or 0.0), reverse=True)
    return rows


def _fmt(v: Any) -> str:
    return "-" if v is None else f"{v}"


def write_outputs(results, scenarios, models, leaderboard, total_cost) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
    (OUT_DIR / "scenarios.json").write_text(
        json.dumps([asdict(s) for s in scenarios], indent=2), encoding="utf-8")

    lb: list[str] = ["# Narrative bake-off leaderboard (NEW prompt)", ""]
    lb.append(f"Judge: {JUDGE_MODEL} | rubric max 16 | "
              f"models {len(models)} | scenarios {len(scenarios)} | "
              f"total spend ${total_cost:.4f}")
    lb.append("")
    lb.append("| Model | Mean | C1 | C2 | C3 | C4 | C5 | C6 | C7 | "
              "Lat(s) | $/call | Fail |")
    lb.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for row in leaderboard:
        cm = row["crit_means"]
        cost = row["mean_cost_usd"]
        cost_str = "-" if cost is None else f"${cost:.6f}"
        lb.append(
            f"| {row['model']} | {_fmt(row['mean_total'])} | "
            f"{_fmt(cm['c1'])} | {_fmt(cm['c2'])} | {_fmt(cm['c3'])} | "
            f"{_fmt(cm['c4'])} | {_fmt(cm['c5'])} | {_fmt(cm['c6'])} | "
            f"{_fmt(cm['c7'])} | {_fmt(row['mean_latency_s'])} | "
            f"{cost_str} | {row['failures']} |"
        )
    (OUT_DIR / "leaderboard.md").write_text("\n".join(lb), encoding="utf-8")

    lines: list[str] = ["# Raw narratives + judge scores", ""]
    by_scn: dict[str, list[CallResult]] = {}
    for r in results:
        by_scn.setdefault(r.scenario_key, []).append(r)
    scn_by_key = {s.key: s for s in scenarios}
    for key, recs in by_scn.items():
        scn = scn_by_key.get(key)
        lines.append(f"## Scenario: {key}")
        if scn:
            top = ", ".join(f"{a.name} ({a.eligibility}, {a.days_rest}d)"
                            for a in scn.ranked_arms)
            lines.append(f"- {scn.label} ({scn.team_id}) {scn.game_date} "
                         f"estimate={scn.is_estimate} | arms: {top}")
            if scn.unavailable_arms:
                lines.append("- unavailable: " + ", ".join(
                    u["name"] for u in scn.unavailable_arms))
        lines.append("")
        for r in sorted(recs, key=lambda x: (x.prompt_tag,
                        -(x.judge_total or -1))):
            tot = "-" if r.judge_total is None else r.judge_total
            sc = "" if not r.scores else " ".join(
                f"{k}={v}" for k, v in r.scores.items())
            tag = "OLD" if r.prompt_tag == "old" else "new"
            lines.append(f"### [{tag}] {r.model} — total {tot}/16  ({sc})")
            if not r.ok:
                lines.append(f"FAILED: {r.error}")
            elif r.narrative:
                lines.append(r.narrative)
                if r.judge_note:
                    lines.append(f"_judge: {r.judge_note}_")
            else:
                lines.append(f"(no narrative) raw: {r.raw_content}")
            lines.append("")
    (OUT_DIR / "scoring_sheet.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote outputs to {OUT_DIR}/ "
          f"(leaderboard.md, scoring_sheet.md, results.json, scenarios.json)")


def write_ab_outputs(results, scenarios, ab_models, total_cost) -> None:
    """A-vs-B comparison: per-(model,variant) base means + the two binary
    sub-checks (ROT on the rotation case, COMM on committee cases) + verbatim
    narratives for the tired-arm, committee, and synthetic-rotation scenarios."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "ab_results.json").write_text(
        json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")

    def agg(model, tag):
        recs = [r for r in results if r.model == model and r.prompt_tag == tag]
        scored = [r for r in recs if r.judge_total is not None]
        totals = [float(r.judge_total) for r in scored]
        # Sub-checks: -1 means N/A; average only the applicable (0/1) ones.
        rots = [r.scores["rot"] for r in scored
                if r.scores and r.scores.get("rot", -1) in (0, 1)]
        comms = [r.scores["comm"] for r in scored
                 if r.scores and r.scores.get("comm", -1) in (0, 1)]
        return {
            "mean_total": _mean(totals),
            "rot_pass": f"{sum(rots)}/{len(rots)}" if rots else "n/a",
            "comm_pass": f"{sum(comms)}/{len(comms)}" if comms else "n/a",
            "mean_latency": _mean([r.latency_s for r in recs
                                   if r.latency_s is not None]),
            "mean_cost": (round(statistics.fmean(
                [r.cost_usd for r in recs if r.cost_usd is not None]), 6)
                if any(r.cost_usd is not None for r in recs) else None),
            "fails": sum(1 for r in recs if not r.ok),
        }

    lines: list[str] = ["# A/B tuning result (variant A vs variant B)", ""]
    lines.append(f"Judge: {JUDGE_MODEL} | base rubric max 16 + binary "
                 f"sub-checks ROT/COMM | temp {AB_TEMPERATURE} | "
                 f"total spend ${total_cost:.4f}")
    lines.append("")
    lines.append("| Model | A base | B base | Δbase | A ROT | B ROT | "
                 "A COMM | B COMM | A lat | B lat | A $/call | B $/call |")
    lines.append("|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|")
    for m in ab_models:
        a, b = agg(m, "A"), agg(m, "B")
        dbase = ("-" if (a["mean_total"] is None or b["mean_total"] is None)
                 else f"{round(b['mean_total'] - a['mean_total'], 2):+}")
        ac = "-" if a["mean_cost"] is None else f"${a['mean_cost']:.6f}"
        bc = "-" if b["mean_cost"] is None else f"${b['mean_cost']:.6f}"
        lines.append(
            f"| {m} | {_fmt(a['mean_total'])} | {_fmt(b['mean_total'])} | "
            f"{dbase} | {a['rot_pass']} | {b['rot_pass']} | "
            f"{a['comm_pass']} | {b['comm_pass']} | "
            f"{_fmt(a['mean_latency'])} | {_fmt(b['mean_latency'])} | "
            f"{ac} | {bc} |"
        )
    lines.append("")
    lines.append("ROT = rotation-rationale sub-check (pass/total, applies when "
                 "#1 has less rest than a lower available arm). COMM = "
                 "committee-honesty sub-check (applies when all Role=Committee "
                 "candidate). Base = mean 7-criterion rubric /16.")

    scn_by_key = {s.key: s for s in scenarios}
    for key in ("rotation_role_synthetic", "tired_arm", "committee"):
        lines.append("")
        lines.append(f"## {key} — verbatim A vs B")
        # Print the ACTUAL rank_context (Role) fed to B per arm: the rotation-
        # rationale sub-check can only fire if the #1 arm carries a real
        # rotation label, NOT "Committee candidate".
        scn = scn_by_key.get(key)
        if scn:
            fed = "; ".join(
                f"{a.name} ({a.days_rest}d)=Role:{a.rank_context or 'Committee candidate'}"
                for a in scn.ranked_arms)
            lines.append(f"_fed rank_context: {fed}_")
        for m in ab_models:
            for tag in ("A", "B"):
                rec = next((r for r in results if r.model == m
                            and r.prompt_tag == tag
                            and r.scenario_key == key), None)
                if rec is None:
                    continue
                tot = "-" if rec.judge_total is None else rec.judge_total
                rot = rec.scores.get("rot") if rec.scores else "-"
                comm = rec.scores.get("comm") if rec.scores else "-"
                lines.append(
                    f"### [{tag}] {m} — {tot}/16 (ROT={rot} COMM={comm})")
                lines.append(rec.narrative or f"(no narrative) {rec.error}")
    (OUT_DIR / "ab_report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote A/B report to {OUT_DIR}/ab_report.md")


def print_scenarios(scenarios) -> None:
    print(f"\n=== {len(scenarios)} SCENARIOS ===")
    for s in scenarios:
        print(f"\n[{s.key}] {s.label} (team {s.team_id}) predicting "
              f"{s.game_date} | est={s.is_estimate} {s.rotation_pattern}")
        for i, a in enumerate(s.ranked_arms, 1):
            print(f"   {i}. {a.name:<22} {a.games_started}GS rest={a.days_rest} "
                  f"lastP={a.last_outing_pitches} [{a.eligibility}]")
        for u in s.unavailable_arms:
            print(f"   x {u['name']} ({u['reason']})")


def print_models(chosen, missing, catalog) -> None:
    print(f"\n=== {len(chosen)} CHOSEN MODELS ===")
    for slug in chosen:
        pp, cp = price_of(catalog, slug)
        print(f"  {slug:<40} ${pp*1e6:.2f}/M in  ${cp*1e6:.2f}/M out")
    if missing:
        print(f"\n=== {len(missing)} NOT IN CATALOG (dropped) ===")
        for slug in missing:
            print(f"  {slug}")


# ── Main ───────────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-scenarios", action="store_true")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--ab", action="store_true",
                    help="A/B run: variant A vs coach's variant B (needs B "
                         "prompt + B_PROMPT_READY=True)")
    args = ap.parse_args()
    if not any([args.build_scenarios, args.list_models, args.smoke,
                args.full, args.ab]):
        args.build_scenarios = args.list_models = True

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    scenarios = build_scenarios(conn)

    if args.build_scenarios or args.smoke or args.full:
        print_scenarios(scenarios)

    if not (args.list_models or args.smoke or args.full or args.ab):
        conn.close()
        return

    api_key = load_api_key()
    catalog = fetch_catalog(api_key)
    chosen, missing = select_models(catalog)
    print_models(chosen, missing, catalog)

    if args.smoke:
        smoke = [m for m in ("anthropic/claude-haiku-4.5",
                             "google/gemini-2.5-flash-lite") if m in chosen]
        run_models = smoke or chosen[:2]
        print(f"\n=== SMOKE: {len(run_models)} models x {len(scenarios)} "
              f"(NEW prompt) ===")
        results = run_generation(api_key, run_models, scenarios, catalog, conn,
                                 prompt_tag="new")
        jcost = run_judge(api_key, results, scenarios, catalog)
        lb = build_leaderboard(results)
        gen_cost = sum(r.cost_usd or 0 for r in results)
        write_outputs(results, scenarios, run_models, lb, gen_cost + jcost)

    if args.full:
        print(f"\n=== FULL: {len(chosen)} models x {len(scenarios)} (NEW) + "
              f"baseline + judge ===")
        results = run_generation(api_key, chosen, scenarios, catalog, conn,
                                 prompt_tag="new")
        baseline_scn = [s for s in scenarios
                        if s.key in ("committee", "tired_arm")]
        baseline_models = [m for m in ("anthropic/claude-haiku-4.5",
                                       "openai/gpt-5.1") if m in chosen]
        print("\n--- OLD-prompt baseline ---")
        baseline = run_generation(api_key, baseline_models, baseline_scn,
                                  catalog, conn, prompt_tag="old")
        results.extend(baseline)
        print("\n--- LLM judge ---")
        jcost = run_judge(api_key, results, scenarios, catalog)
        lb = build_leaderboard(results)
        gen_cost = sum(r.cost_usd or 0 for r in results)
        total = gen_cost + jcost
        write_outputs(results, scenarios, chosen, lb, total)
        print(f"\nTOTAL SPEND: ${total:.4f} "
              f"(generation ${gen_cost:.4f} + judge ${jcost:.4f})")

    if args.ab:
        ab_models = [m for m in ("google/gemini-2.5-flash-lite",
                                 "anthropic/claude-haiku-4.5",
                                 "mistralai/mistral-large-2512")
                     if m in chosen]
        if not B_PROMPT_READY:
            print("\n=== A/B BLOCKED ===\n"
                  "Variant B prompt is still the placeholder. Set "
                  "B_SYSTEM_PROMPT to baseball-coach's enhanced wording and "
                  "flip B_PROMPT_READY=True (and pin AB_TEMPERATURE) before "
                  "running --ab. No spend incurred.")
            conn.close()
            return
        # Add coach's verbatim example as a synthetic rotation-role scenario --
        # the ONLY condition in which B's rotation-rationale lever can fire
        # (no real loaded team produces a differentiated rotation Role; see
        # coach_example_scenario docstring).
        ab_scenarios = scenarios + [coach_example_scenario()]
        print(f"\n=== A/B: {len(ab_models)} models x {len(ab_scenarios)} x "
              f"(A,B) @ temp {AB_TEMPERATURE} "
              f"(incl. 1 synthetic rotation case) ===")
        res_a = run_generation(api_key, ab_models, ab_scenarios, catalog, conn,
                               prompt_tag="A")
        res_b = run_generation(api_key, ab_models, ab_scenarios, catalog, conn,
                               prompt_tag="B")
        results = res_a + res_b
        print("\n--- LLM judge ---")
        jcost = run_judge(api_key, results, ab_scenarios, catalog)
        gen_cost = sum(r.cost_usd or 0 for r in results)
        total = gen_cost + jcost
        write_ab_outputs(results, ab_scenarios, ab_models, total)
        print(f"\nTOTAL SPEND: ${total:.4f} "
              f"(generation ${gen_cost:.4f} + judge ${jcost:.4f})")

    conn.close()


if __name__ == "__main__":
    main()
