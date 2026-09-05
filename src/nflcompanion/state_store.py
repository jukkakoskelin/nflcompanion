"""Read-only access to the draft companion's durable state files."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_DRAFT_STYLES = {
    "sleeper_dynasty": {"platform": "sleeper", "draft_type": "dynasty", "supports_reverse_round": False},
    "espn_snake": {"platform": "espn", "draft_type": "snake", "supports_reverse_round": True},
}


def _strategies_path(state_root: Path) -> Path:
    return state_root / "strategies" / "strategies.json"


def _read_strategy_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"leagues": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("leagues"), dict):
        raise ValueError("Draft strategy store must include a 'leagues' object")
    return payload


def save_draft_strategy(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    draft_style: str,
    name: str,
    strategy: dict[str, Any],
    reverse_round: bool = False,
) -> dict[str, Any]:
    if draft_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported draft style: {draft_style}")
    style = SUPPORTED_DRAFT_STYLES[draft_style]
    if reverse_round and not style["supports_reverse_round"]:
        raise ValueError(f"Draft style {draft_style} does not support reverse round")

    path = _strategies_path(state_root)
    state = _read_strategy_state(path)
    leagues = state.setdefault("leagues", {})
    league_node = leagues.setdefault(str(league_id), {})
    season_node = league_node.setdefault(str(season), {})
    session_config = season_node.setdefault(
        "session",
        {
            "league_id": str(league_id),
            "season": int(season),
            "draft_style": draft_style,
            "platform": style["platform"],
            "draft_type": style["draft_type"],
            "reverse_round": bool(reverse_round),
        },
    )
    if session_config.get("draft_style") != draft_style:
        raise ValueError(
            f"League {league_id} season {season} already configured for {session_config.get('draft_style')}"
        )
    if bool(session_config.get("reverse_round", False)) != bool(reverse_round):
        raise ValueError(
            f"League {league_id} season {season} already configured with reverse_round="
            f"{session_config.get('reverse_round')}"
        )

    strategies = season_node.setdefault("strategies", [])
    strategy_record = {
        "strategy_id": f"{league_id}-{season}-{len(strategies) + 1}",
        "name": name,
        "created_at": datetime.now(UTC).isoformat(),
        "strategy": strategy,
    }
    strategies.append(strategy_record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return strategy_record


def strategies_for_session(state_root: Path, *, league_id: str, season: int) -> dict[str, Any]:
    path = _strategies_path(state_root)
    state = _read_strategy_state(path)
    league_node = state["leagues"].get(str(league_id))
    if not isinstance(league_node, dict):
        raise FileNotFoundError(f"No draft strategies stored for league {league_id}")
    season_node = league_node.get(str(season))
    if not isinstance(season_node, dict):
        raise FileNotFoundError(f"No draft strategies stored for league {league_id} season {season}")
    session_config = season_node.get("session")
    strategies = season_node.get("strategies")
    if not isinstance(session_config, dict) or not isinstance(strategies, list):
        raise ValueError("Draft strategy season entry must include session config and strategy list")
    return {"session": session_config, "strategies": strategies}


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
