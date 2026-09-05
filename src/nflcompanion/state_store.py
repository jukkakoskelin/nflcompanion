"""Read-only access to the draft companion's durable state files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def latest_snapshot(state_root: Path, provider: str = "sleeper") -> Path:
    snapshots = sorted(
        (state_root / "players" / "raw").glob(f"{provider}-players-*.json"),
        reverse=True,
    )
    if not snapshots:
        raise FileNotFoundError(
            f"No {provider} player snapshot found under {state_root / 'players' / 'raw'}"
        )
    return snapshots[0]


def load_players(snapshot: Path) -> list[dict[str, Any]]:
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Player snapshot must be a JSON object keyed by provider id")
    players = []
    for provider_id, record in payload.items():
        if isinstance(record, dict):
            player = dict(record)
            player["provider_id"] = str(record.get("player_id") or provider_id)
            players.append(player)
    return players


def query_players(
    players: Iterable[dict[str, Any]],
    *,
    name: str | None = None,
    position: str | None = None,
    team: str | None = None,
    active_only: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    name_filter = name.casefold() if name else None
    position_filter = position.upper() if position else None
    team_filter = team.upper() if team else None
    matches = []
    for player in players:
        full_name = str(player.get("full_name") or "")
        positions = {str(value).upper() for value in player.get("fantasy_positions") or []}
        if name_filter and name_filter not in full_name.casefold():
            continue
        if position_filter and position_filter not in positions:
            continue
        if team_filter and str(player.get("team") or "").upper() != team_filter:
            continue
        if active_only and not player.get("active", False):
            continue
        matches.append(
            {
                "provider_id": player["provider_id"],
                "full_name": full_name,
                "position": player.get("position"),
                "fantasy_positions": sorted(positions),
                "team": player.get("team"),
                "status": player.get("status"),
                "active": bool(player.get("active", False)),
                "injury_status": player.get("injury_status"),
                "search_rank": player.get("search_rank"),
                "espn_id": player.get("espn_id"),
            }
        )
    return matches[: max(0, limit)]
