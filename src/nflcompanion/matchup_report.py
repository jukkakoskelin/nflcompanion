"""Shared formatting for projected weekly matchup comparisons."""

from collections.abc import Mapping, Sequence
from math import isfinite
from typing import Any


def get_matchup_projections(
    provider: Any,
    week: int,
    platform: str,
    matchup_data: Mapping[str, Mapping[str, Any]],
    player_id_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return projections keyed by the player IDs used in the player snapshot."""
    projections = dict(provider.get_projections(week))
    if platform != "espn":
        return projections

    id_map = player_id_map or {}
    for side in ("user", "opponent"):
        lineup = matchup_data.get(side) or {}
        for player_id, value in (lineup.get("player_projected") or {}).items():
            mapped_id = id_map.get(str(player_id), str(player_id))
            projections[mapped_id] = value
    return projections


def build_projection_comparison(
    user_starters: Sequence[Any],
    opponent_starters: Sequence[Any],
    players: Mapping[str, Mapping[str, Any]],
    projections: Mapping[str, Any],
    *,
    platform: str,
) -> list[str]:
    """Format starter projections and a projected edge, excluding missing values."""
    scoring = "Sleeper half-PPR" if platform == "sleeper" else "ESPN league scoring"
    report = [
        "### Projected Matchup Comparison",
        "",
        f"{scoring} projections are estimates, not actual scores.",
        "",
    ]
    team_totals: list[tuple[str, float | None, int, int]] = []

    for label, starter_ids in (
        ("Your", user_starters),
        ("Opponent", opponent_starters),
    ):
        total = 0.0
        projected_count = 0
        player_lines = []
        if not starter_ids:
            player_lines.append("- No starters listed.")

        for player_id in starter_ids:
            pid = str(player_id)
            player = players.get(pid, {})
            name = (
                player.get("full_name")
                or player.get("first_name")
                or f"Player {pid}"
            )
            position = player.get("position") or "UNK"
            team = player.get("team") or "FA"
            projection = _numeric_projection(projections.get(pid))
            injury = str(player.get("injury_status") or "").lower()
            injury_flag = (
                f" (Injury: {player.get('injury_status')})"
                if injury in ("out", "questionable", "doubtful")
                else ""
            )
            if projection is None:
                projection_text = "projection unavailable"
            else:
                total += projection
                projected_count += 1
                projection_text = f"{projection:.1f} projected pts"
            player_lines.append(
                f"- **{name}** ({position} - {team}){injury_flag} - {projection_text}"
            )

        complete = projected_count == len(starter_ids) and bool(starter_ids)
        if complete:
            total_value: float | None = total
            total_text = (
                f"{total:.1f} pts "
                f"({projected_count}/{len(starter_ids)} starters projected)"
            )
        elif projected_count:
            total_value = None
            total_text = (
                f"{total:.1f} pts partial subtotal "
                f"({projected_count}/{len(starter_ids)} starters projected)"
            )
        else:
            total_value = None
            total_text = f"unavailable (0/{len(starter_ids)} starters projected)"
        report.extend(
            [
                f"- **{label} projected total:** {total_text}",
                "",
                f"#### {label} Starters",
                "",
                *player_lines,
                "",
            ]
        )
        team_totals.append((label, total_value, projected_count, len(starter_ids)))

    user_total = team_totals[0][1]
    opponent_total = team_totals[1][1]
    if user_total is None or opponent_total is None:
        missing_count = sum(
            team_size - projected_count
            for _, _, projected_count, team_size in team_totals
        )
        if any(team_size == 0 for _, _, _, team_size in team_totals):
            reason = "one or both lineups have no listed starters"
        else:
            noun = "starter" if missing_count == 1 else "starters"
            reason = f"missing projections for {missing_count} {noun}"
        report.append(f"- **Projected edge:** unavailable: {reason}.")
    else:
        difference = user_total - opponent_total
        if difference > 0.05:
            edge = f"Your team by {difference:.1f} pts"
        elif difference < -0.05:
            edge = f"Opponent by {abs(difference):.1f} pts"
        else:
            edge = f"Even ({user_total:.1f} pts each)"
        report.append(f"- **Projected edge:** {edge}.")

    return report


def _numeric_projection(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        projection = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return projection if isfinite(projection) else None
