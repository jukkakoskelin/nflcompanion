"""Read-only access to the draft companion's durable state files."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_DRAFT_STYLES = {
    "sleeper_dynasty": {"platform": "sleeper", "draft_type": "dynasty", "supports_reverse_round": False},
    "espn_snake": {"platform": "espn", "draft_type": "snake", "supports_reverse_round": True},
}
_MISSING = object()


def _strategies_path(state_root: Path) -> Path:
    return state_root / "strategies" / "strategies.json"


def _read_strategy_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"leagues": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("leagues"), dict):
        raise ValueError("Draft strategy store must include a 'leagues' object")
    return payload


def _validate_session_config(session_config: dict[str, Any]) -> None:
    stored_style = str(session_config.get("draft_style") or "")
    if stored_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported stored draft style: {stored_style}")
    style = SUPPORTED_DRAFT_STYLES[stored_style]
    if session_config.get("platform") != style["platform"] or session_config.get("draft_type") != style["draft_type"]:
        raise ValueError("Stored draft session metadata does not match draft style")
    if bool(session_config.get("reverse_round", False)) and not style["supports_reverse_round"]:
        raise ValueError("Stored draft session uses reverse round for unsupported draft style")


def _validate_session_identity(session_config: dict[str, Any], league_id: str, season: int) -> None:
    if str(session_config.get("league_id")) != str(league_id):
        raise ValueError("Stored draft session league_id does not match strategy bucket")
    try:
        stored_season = int(session_config.get("season"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Stored draft session season must be an integer") from exc
    if stored_season != int(season):
        raise ValueError("Stored draft session season does not match strategy bucket")


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
    leagues = state.get("leagues")
    if not isinstance(leagues, dict):
        raise ValueError("Draft strategy store 'leagues' must be an object")
    league_key = str(league_id)
    season_key = str(season)
    existing_league_node = leagues.get(league_key, _MISSING)
    if existing_league_node is _MISSING:
        league_node: dict[str, Any] = {}
    elif not isinstance(existing_league_node, dict):
        raise ValueError(f"Draft strategy league entry for {league_id} must be an object")
    else:
        league_node = dict(existing_league_node)

    existing_season_node = league_node.get(season_key, _MISSING)
    if existing_season_node is _MISSING:
        season_node: dict[str, Any] = {}
    elif not isinstance(existing_season_node, dict):
        raise ValueError(f"Draft strategy season entry for {league_id} {season} must be an object")
    else:
        season_node = dict(existing_season_node)

    session_config = season_node.get("session")
    if session_config is None:
        session_config = {
            "league_id": str(league_id),
            "season": int(season),
            "draft_style": draft_style,
            "platform": style["platform"],
            "draft_type": style["draft_type"],
            "reverse_round": bool(reverse_round),
        }
    elif not isinstance(session_config, dict):
        raise ValueError("Draft strategy season entry 'session' must be an object")

    _validate_session_config(session_config)
    _validate_session_identity(session_config, league_id, season)
    if session_config.get("draft_style") != draft_style:
        raise ValueError(
            f"League {league_id} season {season} already configured for {session_config.get('draft_style')}"
        )
    if session_config.get("platform") != style["platform"] or session_config.get("draft_type") != style["draft_type"]:
        raise ValueError(
            f"League {league_id} season {season} has inconsistent session style metadata"
        )
    if bool(session_config.get("reverse_round", False)) != bool(reverse_round):
        raise ValueError(
            f"League {league_id} season {season} already configured with reverse_round="
            f"{session_config.get('reverse_round')}"
        )

    strategies = season_node.get("strategies")
    if strategies is None:
        strategies = []
    if not isinstance(strategies, list):
        raise ValueError("Draft strategy season entry 'strategies' must be a list")
    next_id = 1
    for existing in strategies:
        if not isinstance(existing, dict):
            raise ValueError("Draft strategy records must be objects")
        existing_number = existing.get("strategy_number")
        if isinstance(existing_number, int) and existing_number > 0:
            next_id = max(next_id, existing_number + 1)
            continue
        strategy_id = str(existing.get("strategy_id") or "")
        if strategy_id.startswith("strategy-") and strategy_id.removeprefix("strategy-").isdigit():
            suffix = strategy_id.removeprefix("strategy-")
            next_id = max(next_id, int(suffix) + 1)
    strategy_record = {
        "strategy_id": f"strategy-{next_id}",
        "strategy_number": next_id,
        "name": name,
        "created_at": datetime.now(UTC).isoformat(),
        "strategy": deepcopy(strategy),
    }
    strategies.append(strategy_record)
    season_node["session"] = session_config
    season_node["strategies"] = strategies
    league_node[season_key] = season_node
    leagues[league_key] = league_node
    state["leagues"] = leagues
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return deepcopy(strategy_record)


def strategies_for_session(state_root: Path, *, league_id: str, season: int) -> dict[str, Any]:
    path = _strategies_path(state_root)
    state = _read_strategy_state(path)
    league_node = state["leagues"].get(str(league_id), _MISSING)
    if league_node is _MISSING:
        return {"session": None, "strategies": []}
    if not isinstance(league_node, dict):
        raise ValueError(f"Draft strategy league entry for {league_id} must be an object")
    season_node = league_node.get(str(season), _MISSING)
    if season_node is _MISSING:
        return {"session": None, "strategies": []}
    if not isinstance(season_node, dict):
        raise ValueError(f"Draft strategy season entry for {league_id} {season} must be an object")
    session_config = season_node.get("session")
    strategies = season_node.get("strategies")
    if not isinstance(session_config, dict) or not isinstance(strategies, list):
        raise ValueError("Draft strategy season entry must include session config and strategy list")
    for strategy in strategies:
        if not isinstance(strategy, dict):
            raise ValueError("Draft strategy records must be objects")
    _validate_session_config(session_config)
    _validate_session_identity(session_config, league_id, season)
    return {"session": deepcopy(session_config), "strategies": deepcopy(strategies)}


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
