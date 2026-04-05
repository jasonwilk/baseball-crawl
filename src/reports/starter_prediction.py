"""Deterministic rotation analysis engine (Tier 1).

Analyzes structured pitching history and produces a ``StarterPrediction``
containing a named prediction (or committee assessment), a rest/availability
table, rotation pattern classification, confidence tier, and recent game logs.

This engine is a pure function with no DB access, no HTTP calls, no side
effects.  It receives the pitcher profiles dict from
``build_pitcher_profiles()`` and the raw pitching history list from
``get_pitching_history()``.
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

_MIN_GAMES_FOR_ROTATION = 4
_PRIMARY_STARTER_GS_RATIO = 0.6
_PRIMARY_STARTER_MIN_GS = 2
_ACE_DOMINANT_THRESHOLD = 0.6
_TWO_MAN_THRESHOLD = 0.3
_HIGH_CONFIDENCE_RATIO = 2.0
_K9_ALTERNATIVE_DELTA = 2.0
_COMMITTEE_TOP_THRESHOLD = 0.30
_HIGH_PITCH_EXCLUSION = 75
_SHORT_REST_DAYS = 4
_WITHIN_1_DAY_REST = 1
_AVAILABILITY_UNKNOWN_DAYS = 10
_LOW_PITCH_THRESHOLD = 50
_ACE_HEAVY_USAGE_GS_PCT = 0.70
_TOURNAMENT_WINDOW_DAYS = 7
_TOURNAMENT_MIN_GAMES = 3
_MAX_RECENT_STARTS = 5
_MIN_RECENT_STARTS = 3
_REST_TABLE_SIZE = 3
_BULLPEN_SIZE = 3
_CANDIDATES_SIZE = 3


# ── Dataclass ───────────────────────────────────────────────────────────


@dataclass
class StarterPrediction:
    """Output of the deterministic rotation analysis engine."""

    confidence: str  # "high", "moderate", "low", "suppress"
    predicted_starter: dict[str, Any] | None = None
    alternative: dict[str, Any] | None = None
    top_candidates: list[dict[str, Any]] = field(default_factory=list)
    rotation_pattern: str = "committee"
    rest_table: list[dict[str, Any]] = field(default_factory=list)
    bullpen_order: list[dict[str, Any]] = field(default_factory=list)
    data_note: str | None = None


# ── Role classification ─────────────────────────────────────────────────


def _classify_role(profile: dict) -> str:
    """Classify a pitcher as primary_starter, spot_starter, or reliever."""
    gs = profile["total_starts"]
    g = profile["total_games"]
    if g == 0:
        return "reliever"
    ratio = gs / g
    if ratio >= _PRIMARY_STARTER_GS_RATIO and gs >= _PRIMARY_STARTER_MIN_GS:
        return "primary_starter"
    if gs >= 1:
        return "spot_starter"
    return "reliever"


# ── Rotation detection ──────────────────────────────────────────────────


def _detect_rotation_pattern(
    profiles: dict[str, dict],
    total_team_games: int,
) -> str:
    """Detect the rotation pattern type from pitcher profiles."""
    if total_team_games == 0:
        return "committee"

    starters = [
        (pid, p["total_starts"])
        for pid, p in profiles.items()
        if p["total_starts"] > 0
    ]
    if not starters:
        return "committee"

    starters.sort(key=lambda x: x[1], reverse=True)
    top_pct = starters[0][1] / total_team_games

    if top_pct >= _ACE_DOMINANT_THRESHOLD:
        return "ace-dominant"

    if len(starters) >= 2:
        second_pct = starters[1][1] / total_team_games
        if top_pct >= _TWO_MAN_THRESHOLD and second_pct >= _TWO_MAN_THRESHOLD:
            if len(starters) >= 3:
                third_pct = starters[2][1] / total_team_games
                if third_pct >= 0.20:
                    return "3-man rotation"
            return "2-man rotation"

    return "committee"


# ── Rest / availability helpers ─────────────────────────────────────────


def _is_excluded_within_1_day(
    profile: dict, latest_game_date: str,
) -> bool:
    """Check if pitcher's last appearance was within 1 calendar day."""
    apps = profile.get("appearances", [])
    if not apps:
        return False
    last_date_str = apps[-1].get("game_date")
    if not last_date_str:
        return False
    try:
        last_date = datetime.date.fromisoformat(last_date_str)
        latest = datetime.date.fromisoformat(latest_game_date)
        return (latest - last_date).days <= _WITHIN_1_DAY_REST
    except (ValueError, TypeError):
        return False


def _is_excluded_high_pitch_short_rest(
    profile: dict, latest_game_date: str,
) -> bool:
    """75+ pitches with fewer than 4 days rest -> excluded."""
    apps = profile.get("appearances", [])
    if not apps:
        return False
    last = apps[-1]
    pitches = last.get("pitches") or 0
    if pitches < _HIGH_PITCH_EXCLUSION:
        return False
    last_date_str = last.get("game_date")
    if not last_date_str:
        return False
    try:
        last_date = datetime.date.fromisoformat(last_date_str)
        latest = datetime.date.fromisoformat(latest_game_date)
        days_rest = (latest - last_date).days
        return days_rest < _SHORT_REST_DAYS
    except (ValueError, TypeError):
        return False


def _build_reasoning(
    profile: dict,
    role: str,
    rotation_pattern: str,
    latest_game_date: str,
    total_team_games: int,
    rank_context: str | None = None,
) -> str:
    """Build a plain-English reasoning string for a candidate."""
    parts: list[str] = []

    if rank_context:
        parts.append(rank_context)

    # Rest info
    apps = profile.get("appearances", [])
    if apps:
        last = apps[-1]
        last_date_str = last.get("game_date")
        if last_date_str:
            try:
                days = (
                    datetime.date.fromisoformat(latest_game_date)
                    - datetime.date.fromisoformat(last_date_str)
                ).days
                parts.append(f"{days} days rest")
            except (ValueError, TypeError):
                pass

        pitches = last.get("pitches")
        if pitches is not None:
            parts.append(f"{pitches} pitches last outing")

    # Role-specific flags
    if role == "spot_starter":
        parts.append("spot starter -- recent start is anomalous")

    # 10+ day gap
    if apps:
        last_date_str = apps[-1].get("game_date")
        if last_date_str:
            try:
                days = (
                    datetime.date.fromisoformat(latest_game_date)
                    - datetime.date.fromisoformat(last_date_str)
                ).days
                if days >= _AVAILABILITY_UNKNOWN_DAYS:
                    parts.append("availability unknown")
            except (ValueError, TypeError):
                pass

    # High/low pitch count flags
    if apps:
        last = apps[-1]
        pitches = last.get("pitches")
        if pitches is not None:
            avg_pitches = _pitcher_avg_pitches(profile)
            if pitches < _LOW_PITCH_THRESHOLD:
                parts.append("low pitch count last outing")
            elif avg_pitches is not None and pitches > avg_pitches:
                parts.append("high pitch count last outing")

    # Ace heavy usage warning
    gs = profile["total_starts"]
    if total_team_games > 0 and gs / total_team_games >= _ACE_HEAVY_USAGE_GS_PCT:
        parts.append("heavy usage")

    return ", ".join(parts) if parts else "insufficient data"


def _pitcher_avg_pitches(profile: dict) -> float | None:
    """Average pitches across all appearances with non-null pitch counts."""
    apps = profile.get("appearances", [])
    counts = [a["pitches"] for a in apps if a.get("pitches") is not None]
    if not counts:
        return None
    return sum(counts) / len(counts)


# ── Recent starts ───────────────────────────────────────────────────────


def _recent_starts(profile: dict, n: int = _MAX_RECENT_STARTS) -> list[dict]:
    """Return the last n starts with game log fields."""
    starts = profile.get("starts", [])
    recent = starts[-n:]
    result = []
    for i, s in enumerate(recent):
        # rest_days_from_previous_start
        rest_from_prev_start: int | None = None
        idx_in_starts = starts.index(s)
        if idx_in_starts > 0:
            prev = starts[idx_in_starts - 1]
            try:
                d1 = datetime.date.fromisoformat(prev["game_date"])
                d2 = datetime.date.fromisoformat(s["game_date"])
                rest_from_prev_start = (d2 - d1).days
            except (ValueError, TypeError):
                pass
        result.append({
            "game_date": s.get("game_date"),
            "ip_outs": s.get("ip_outs"),
            "pitches": s.get("pitches"),
            "so": s.get("so"),
            "bb": s.get("bb"),
            "decision": s.get("decision"),
            "rest_days_from_previous_start": rest_from_prev_start,
        })
    return result


# ── Rest table ──────────────────────────────────────────────────────────


def _build_rest_table(
    profiles: dict[str, dict],
    roles: dict[str, str],
    workload: dict[str, dict] | None,
) -> list[dict]:
    """Build rest table: top 1-2 starters by GS + highest-appearance relievers."""
    # Starters sorted by GS descending
    starters = sorted(
        [(pid, p) for pid, p in profiles.items() if p["total_starts"] > 0],
        key=lambda x: x[1]["total_starts"],
        reverse=True,
    )
    # Relievers sorted by total appearances descending
    relievers = sorted(
        [(pid, p) for pid, p in profiles.items() if p["total_starts"] == 0],
        key=lambda x: x[1]["total_games"],
        reverse=True,
    )

    selected: list[tuple[str, dict]] = []
    # Top 1-2 starters
    for pid, p in starters[:2]:
        selected.append((pid, p))
    # Fill to 3 with relievers
    for pid, p in relievers:
        if len(selected) >= _REST_TABLE_SIZE:
            break
        selected.append((pid, p))

    result = []
    for pid, p in selected:
        apps = p.get("appearances", [])
        last_pitches = apps[-1].get("pitches") if apps else None

        entry: dict[str, Any] = {
            "name": f"{p['first_name']} {p['last_name']}",
            "jersey_number": p.get("jersey_number"),
            "games_started": p["total_starts"],
            "last_outing_date": None,
            "days_since_last_appearance": None,
            "last_outing_pitches": last_pitches,
            "workload_7d": None,
        }

        if workload and pid in workload:
            wl = workload[pid]
            entry["last_outing_date"] = wl.get("last_outing_date")
            entry["days_since_last_appearance"] = wl.get("last_outing_days_ago")
            entry["workload_7d"] = wl.get("pitches_7d")

        result.append(entry)

    return result


# ── Bullpen order ───────────────────────────────────────────────────────


def _build_bullpen_order(
    profiles: dict[str, dict],
    history: list[dict],
) -> list[dict]:
    """Rank relievers by frequency of first-relief-appearance (appearance_order=2)."""
    # Count appearance_order == 2 per player
    relief_counts: dict[str, int] = {}
    total_games_with_relief = set()
    for row in history:
        if row.get("appearance_order") == 2:
            pid = row["player_id"]
            relief_counts[pid] = relief_counts.get(pid, 0) + 1
            total_games_with_relief.add(row["game_id"])

    if not relief_counts:
        return []

    games_sampled = len(total_games_with_relief)
    ranked = sorted(relief_counts.items(), key=lambda x: x[1], reverse=True)

    result = []
    for pid, count in ranked[:_BULLPEN_SIZE]:
        p = profiles.get(pid, {})
        result.append({
            "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
            "jersey_number": p.get("jersey_number"),
            "frequency": count,
            "games_sampled": games_sampled,
        })
    return result


# ── Tournament density ──────────────────────────────────────────────────


def _check_tournament_density(history: list[dict]) -> bool:
    """Check if 3+ games in the last 7 days fall on consecutive/near-consecutive days."""
    if not history:
        return False

    # Get unique game dates from last 7 days of game history
    all_dates = sorted(set(r["game_date"] for r in history))
    if not all_dates:
        return False

    latest_str = all_dates[-1]
    try:
        latest = datetime.date.fromisoformat(latest_str)
    except (ValueError, TypeError):
        return False

    cutoff = latest - datetime.timedelta(days=_TOURNAMENT_WINDOW_DAYS - 1)
    recent_dates = [
        datetime.date.fromisoformat(d)
        for d in all_dates
        if datetime.date.fromisoformat(d) >= cutoff
    ]

    if len(recent_dates) < _TOURNAMENT_MIN_GAMES:
        return False

    # Check if games are on consecutive or near-consecutive days (gaps of 0-1)
    consecutive_count = 1
    for i in range(1, len(recent_dates)):
        gap = (recent_dates[i] - recent_dates[i - 1]).days
        if gap <= 1:
            consecutive_count += 1
        else:
            consecutive_count = 1
        if consecutive_count >= _TOURNAMENT_MIN_GAMES:
            return True

    return False


# ── Sequence-based likelihood ───────────────────────────────────────────


def _compute_rotation_likelihoods(
    profiles: dict[str, dict],
    history: list[dict],
    roles: dict[str, str],
    latest_game_date: str,
) -> dict[str, float]:
    """Compute internal likelihood scores for each starter candidate.

    Weights: 70% rotation sequence, 30% matchup factors (approximated by
    recency and rest).
    """
    # Extract chronological starter sequence from history
    starter_sequence: list[str] = []
    seen_games: set[str] = set()
    for row in history:
        gid = row["game_id"]
        if gid in seen_games:
            continue
        seen_games.add(gid)
        # Find the starter for this game
        game_rows = [r for r in history if r["game_id"] == gid]
        starter_row = None
        for gr in game_rows:
            if gr.get("appearance_order") == 1:
                starter_row = gr
                break
        if starter_row is None:
            # Fallback: most IP
            game_rows_sorted = sorted(
                game_rows, key=lambda x: x.get("ip_outs") or 0, reverse=True
            )
            if game_rows_sorted:
                starter_row = game_rows_sorted[0]
        if starter_row:
            starter_sequence.append(starter_row["player_id"])

    if not starter_sequence:
        return {}

    likelihoods: dict[str, float] = {}

    # Rotation sequence signal (70% weight)
    # Look at last 2 full cycles to predict next
    unique_starters = list(dict.fromkeys(starter_sequence))
    n_unique = len(unique_starters)

    if n_unique == 1:
        # Ace dominant -- single pitcher gets all weight
        likelihoods[unique_starters[0]] = 0.70
    elif n_unique >= 2:
        # Detect repeating pattern from recent history
        cycle_len = n_unique
        # Use last 2*cycle_len games to detect pattern
        recent = starter_sequence[-(2 * cycle_len):]
        if len(recent) >= cycle_len:
            # Next in sequence
            last_starter = recent[-1]
            # Find the position of last_starter in the typical cycle
            # Build cycle from the first occurrence order in recent history
            cycle = list(dict.fromkeys(recent))
            if last_starter in cycle:
                idx = cycle.index(last_starter)
                next_idx = (idx + 1) % len(cycle)
                predicted_next = cycle[next_idx]
                # Distribute likelihood
                for pid in cycle:
                    if pid == predicted_next:
                        likelihoods[pid] = 0.70
                    else:
                        likelihoods[pid] = 0.70 * 0.1 / max(len(cycle) - 1, 1)
            else:
                for pid in cycle:
                    likelihoods[pid] = 0.70 / len(cycle)
        else:
            for pid in unique_starters:
                likelihoods[pid] = 0.70 / n_unique

    # Matchup/rest signal (30% weight) -- favor rested pitchers
    for pid, profile in profiles.items():
        if profile["total_starts"] == 0:
            continue
        apps = profile.get("appearances", [])
        if not apps:
            continue
        last_date_str = apps[-1].get("game_date")
        if not last_date_str:
            continue
        try:
            days = (
                datetime.date.fromisoformat(latest_game_date)
                - datetime.date.fromisoformat(last_date_str)
            ).days
            # More rest = more available. Normalize to 0-0.30.
            rest_score = min(days / 7.0, 1.0) * 0.30
            likelihoods[pid] = likelihoods.get(pid, 0) + rest_score
        except (ValueError, TypeError):
            pass

    return likelihoods


# ── Main engine ─────────────────────────────────────────────────────────


def compute_starter_prediction(
    pitcher_profiles: dict[str, dict],
    pitching_history: list[dict],
    workload: dict[str, dict] | None = None,
) -> StarterPrediction:
    """Analyze pitching history and produce a starter prediction.

    Args:
        pitcher_profiles: Output from ``build_pitcher_profiles()``.
        pitching_history: Output from ``get_pitching_history()``.
        workload: Output from ``get_pitching_workload()`` (optional).

    Returns:
        ``StarterPrediction`` dataclass with prediction, rest table,
        rotation pattern, and confidence tier.
    """
    # Count unique completed games
    game_ids = sorted(set(r["game_id"] for r in pitching_history))
    total_team_games = len(game_ids)

    # ── Suppress: fewer than 4 games ────────────────────────────────
    if total_team_games < _MIN_GAMES_FOR_ROTATION:
        if total_team_games <= 2:
            note = (
                f"Rest intervals not yet available -- "
                f"{total_team_games} game(s) played"
            )
        else:
            note = (
                "Rotation pattern unclear -- 3 games played, "
                "rest data accumulating"
            )
        roles = {pid: _classify_role(p) for pid, p in pitcher_profiles.items()}
        return StarterPrediction(
            confidence="suppress",
            rest_table=_build_rest_table(pitcher_profiles, roles, workload),
            bullpen_order=_build_bullpen_order(pitcher_profiles, pitching_history),
            data_note=note,
        )

    # ── Classify roles ──────────────────────────────────────────────
    roles: dict[str, str] = {}
    for pid, profile in pitcher_profiles.items():
        roles[pid] = _classify_role(profile)

    # ── Detect rotation pattern ─────────────────────────────────────
    rotation_pattern = _detect_rotation_pattern(
        pitcher_profiles, total_team_games
    )

    # ── Latest game date for rest calculations ──────────────────────
    all_dates = sorted(set(r["game_date"] for r in pitching_history))
    latest_game_date = all_dates[-1] if all_dates else ""

    # ── Compute likelihoods ─────────────────────────────────────────
    likelihoods = _compute_rotation_likelihoods(
        pitcher_profiles, pitching_history, roles, latest_game_date
    )

    # ── Apply exclusions ────────────────────────────────────────────
    excluded: set[str] = set()
    for pid, profile in pitcher_profiles.items():
        if profile["total_starts"] == 0:
            continue
        if _is_excluded_within_1_day(profile, latest_game_date):
            excluded.add(pid)
        if _is_excluded_high_pitch_short_rest(profile, latest_game_date):
            excluded.add(pid)

    # Remove excluded from likelihoods
    for pid in excluded:
        likelihoods.pop(pid, None)

    # ── Build candidates ────────────────────────────────────────────
    # Sort by likelihood descending
    sorted_candidates = sorted(
        [
            (pid, score)
            for pid, score in likelihoods.items()
            if pitcher_profiles[pid]["total_starts"] > 0
        ],
        key=lambda x: x[1],
        reverse=True,
    )

    candidates: list[dict[str, Any]] = []
    for pid, score in sorted_candidates[:_CANDIDATES_SIZE]:
        profile = pitcher_profiles[pid]
        role = roles[pid]
        rank_context = None
        if rotation_pattern == "ace-dominant" and candidates == []:
            # Only label as "Ace starter" if this pitcher actually has the
            # highest GS count (the actual ace may have been excluded).
            max_gs = max(p["total_starts"] for p in pitcher_profiles.values())
            if profile["total_starts"] == max_gs:
                rank_context = "Ace starter"
            else:
                rank_context = "Next available starter"
        elif rotation_pattern == "2-man rotation":
            rank_context = "Next in 2-man rotation"
        elif rotation_pattern == "3-man rotation":
            rank_context = "Next in 3-man rotation"
        elif rotation_pattern == "committee":
            rank_context = "Committee candidate"

        reasoning = _build_reasoning(
            profile, role, rotation_pattern, latest_game_date,
            total_team_games, rank_context=rank_context,
        )
        candidates.append({
            "player_id": pid,
            "name": f"{profile['first_name']} {profile['last_name']}",
            "jersey_number": profile.get("jersey_number"),
            "likelihood": round(score, 3),
            "reasoning": reasoning,
            "games_started": profile["total_starts"],
            "recent_starts": _recent_starts(profile),
        })

    # ── Confidence tier ─────────────────────────────────────────────
    predicted_starter: dict[str, Any] | None = None
    alternative: dict[str, Any] | None = None
    confidence: str

    if not candidates:
        confidence = "low"
    elif len(candidates) == 1:
        confidence = "high"
        predicted_starter = candidates[0]
    else:
        top = candidates[0]
        second = candidates[1]

        # Committee check: top candidate has <= 30% of total starts
        if top["games_started"] / max(total_team_games, 1) <= _COMMITTEE_TOP_THRESHOLD:
            confidence = "low"
        elif top["likelihood"] >= _HIGH_CONFIDENCE_RATIO * second["likelihood"]:
            confidence = "high"
            predicted_starter = top

            # Check moderate trigger: rested starter with K/9 > 2.0 higher
            top_pid = top["player_id"]
            top_k9 = pitcher_profiles[top_pid].get("season_k9") or 0
            for cand in candidates[1:]:
                cand_pid = cand["player_id"]
                cand_role = roles.get(cand_pid, "reliever")
                if cand_role not in ("primary_starter", "spot_starter"):
                    continue
                if cand_pid in excluded:
                    continue
                cand_k9 = pitcher_profiles[cand_pid].get("season_k9") or 0
                if cand_k9 - top_k9 > _K9_ALTERNATIVE_DELTA:
                    confidence = "moderate"
                    alternative = cand
                    break
        else:
            # Check moderate: clear rotation pick but close
            if rotation_pattern != "committee":
                confidence = "moderate"
                predicted_starter = top

                # K/9 alternative check
                top_pid = top["player_id"]
                top_k9 = pitcher_profiles[top_pid].get("season_k9") or 0
                for cand in candidates[1:]:
                    cand_pid = cand["player_id"]
                    cand_role = roles.get(cand_pid, "reliever")
                    if cand_role not in ("primary_starter", "spot_starter"):
                        continue
                    if cand_pid in excluded:
                        continue
                    cand_k9 = pitcher_profiles[cand_pid].get("season_k9") or 0
                    if cand_k9 - top_k9 > _K9_ALTERNATIVE_DELTA:
                        alternative = cand
                        break
                if alternative is None:
                    alternative = second
            else:
                confidence = "low"

    # ── Data note ───────────────────────────────────────────────────
    data_note: str | None = None
    if _check_tournament_density(pitching_history):
        data_note = (
            "Compressed schedule detected -- rotation predictions "
            "less reliable."
        )

    # ── Rest table ──────────────────────────────────────────────────
    rest_table = _build_rest_table(pitcher_profiles, roles, workload)

    # ── Bullpen order ───────────────────────────────────────────────
    bullpen_order = _build_bullpen_order(pitcher_profiles, pitching_history)

    return StarterPrediction(
        confidence=confidence,
        predicted_starter=predicted_starter,
        alternative=alternative,
        top_candidates=candidates,
        rotation_pattern=rotation_pattern,
        rest_table=rest_table,
        bullpen_order=bullpen_order,
        data_note=data_note,
    )
