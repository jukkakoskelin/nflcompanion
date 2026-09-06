"""Model Context Protocol (MCP) server for nflcompanion tools."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from nflcompanion.draft_companion import (
    calculate_roster_summary,
    create_draft_session,
    load_draft_session,
    next_pick_for_slot,
    next_pick_preview,
    record_observed_pick,
    record_pick,
    recommend_candidates,
    update_living_strategy,
)
from nflcompanion.state_store import (
    latest_snapshot,
    latest_trending_snapshot,
    load_players,
    load_trending,
    query_players,
    query_trending_players,
)

SERVER_NAME = "nflcompanion"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
SLEEPER_TRENDING_URL = "https://api.sleeper.app/v1/players/nfl/trending/{direction}"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def fetch_players(url: str = SLEEPER_PLAYERS_URL, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Sleeper response must be a JSON object keyed by player id")
    return payload


def save_snapshot(payload: dict[str, Any], state_root: Path, retrieved_at: datetime) -> Path:
    stamp = (
        retrieved_at.strftime("%Y-%m-%dT%H%M%S")
        + f"{retrieved_at.microsecond // 1000:03d}Z"
    )
    raw_path = state_root / "players" / "raw" / f"sleeper-players-{stamp}.json"
    manifest_path = state_root / "players" / f"sleeper-players-{stamp}.md"
    _atomic_write(raw_path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    manifest = (
        f"---\nprovider: sleeper\nretrieved_at: {retrieved_at.isoformat()}\n"
        f"endpoint: {SLEEPER_PLAYERS_URL}\nrecord_count: {len(payload)}\nraw_snapshot: "
        f"{raw_path.relative_to(state_root).as_posix()}\n---\n\n"
        "# Sleeper player snapshot\n\n"
        "This is an immutable, read-only provider snapshot. Use the raw JSON "
        "for complete fields and the canonical state reader for queries.\n"
    )
    _atomic_write(manifest_path, manifest)
    return raw_path


def fetch_trending(
    direction: str, *, lookback_hours: int = 24, limit: int = 25, timeout: int = 30
) -> list[dict[str, Any]]:
    if direction not in ("add", "drop"):
        raise ValueError("direction must be 'add' or 'drop'")
    url = f"{SLEEPER_TRENDING_URL.format(direction=direction)}?lookback_hours={lookback_hours}&limit={limit}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError("Sleeper trending response must be a JSON array")
    return payload


def save_trending_snapshot(
    *,
    add_entries: list[dict[str, Any]],
    drop_entries: list[dict[str, Any]],
    state_root: Path,
    retrieved_at: datetime,
    lookback_hours: int = 24,
    limit: int = 25,
) -> Path:
    stamp = (
        retrieved_at.strftime("%Y-%m-%dT%H%M%S")
        + f"{retrieved_at.microsecond // 1000:03d}Z"
    )
    raw_path = state_root / "players" / "trending" / "raw" / f"sleeper-trending-{stamp}.json"
    manifest_path = state_root / "players" / "trending" / f"sleeper-trending-{stamp}.md"
    payload = {
        "provider": "sleeper",
        "retrieved_at": retrieved_at.isoformat(),
        "lookback_hours": lookback_hours,
        "limit": limit,
        "add": add_entries,
        "drop": drop_entries,
    }
    _atomic_write(raw_path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    manifest = (
        "---\nprovider: sleeper\n"
        f"retrieved_at: {retrieved_at.isoformat()}\n"
        f"lookback_hours: {lookback_hours}\n"
        f"limit: {limit}\n"
        f"add_count: {len(add_entries)}\n"
        f"drop_count: {len(drop_entries)}\n"
        "raw_snapshot: "
        f"{raw_path.relative_to(state_root).as_posix()}\n---\n\n"
        "# Sleeper trending player snapshot\n\n"
        "This is an immutable, read-only provider snapshot of add/drop trending "
        "activity. Player trending changes constantly, so a new snapshot is "
        "written on every fetch instead of overwriting the previous one.\n"
    )
    _atomic_write(manifest_path, manifest)
    return raw_path


def _sleeper_api_get(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


TOOLS: list[dict[str, Any]] = [
    {
        "name": "sleeper_ensure_player_state",
        "description": "Check for local Sleeper player state and fetch it from the public API only when absent, or refresh when requested.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "refresh": {
                    "type": "boolean",
                    "description": "Fetch a new snapshot even when local state exists.",
                    "default": False,
                },
                "state_root": {
                    "type": "string",
                    "description": "Root state directory path.",
                    "default": "state",
                },
            },
        },
    },
    {
        "name": "sleeper_query_players",
        "description": "Query the local Sleeper NFL player snapshot by name, position, team, and active status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Substring match for player full name."},
                "position": {"type": "string", "description": "Position abbreviation (e.g., QB, RB, WR)."},
                "team": {"type": "string", "description": "NFL team abbreviation (e.g., GB, KC)."},
                "activeOnly": {"type": "boolean", "description": "Filter for active NFL roster status.", "default": False},
                "limit": {"type": "integer", "description": "Maximum number of results.", "default": 20},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "sleeper_query_trending_players",
        "description": "Query the local Sleeper trending add/drop player snapshot captured at session start (or refresh it).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "enum": ["add", "drop"],
                    "description": "Whether to list trending adds or drops.",
                    "default": "add",
                },
                "position": {"type": "string", "description": "Filter by position abbreviation."},
                "team": {"type": "string", "description": "Filter by NFL team abbreviation."},
                "limit": {"type": "integer", "description": "Maximum number of results.", "default": 25},
                "refresh": {"type": "boolean", "description": "Fetch a new trending snapshot before querying.", "default": False},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_get_session",
        "description": "Get current draft session details, roster composition, position counts, remaining needs, and active living strategy.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_init_session",
        "description": "Initialize a new draft companion session.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season", "draft_style", "team_count", "user_slot"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year (e.g., 2026)."},
                "draft_style": {"type": "string", "description": "e.g., espn_snake or sleeper_dynasty."},
                "team_count": {"type": "integer", "description": "Number of teams in draft."},
                "user_slot": {"type": "integer", "description": "User's draft slot (1-based)."},
                "active_strategy_id": {"type": "string", "description": "ID of active strategy."},
                "strategy_json": {"type": "object", "description": "Inline strategy payload."},
                "reverse_round": {"type": "boolean", "description": "Enable third-round reversal.", "default": False},
                "decision_window_seconds": {"type": "integer", "description": "Decision window per pick.", "default": 90},
                "allow_existing": {
                    "type": "boolean",
                    "description": "Return existing session if already created instead of failing.",
                    "default": True,
                },
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_recommend_candidates",
        "description": "Deterministically score and rank 2-4 draft candidates against active strategy, roster, and trends.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season", "candidates"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 2 to 4 candidate player names or surnames.",
                },
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_record_pick",
        "description": "Record a confirmed draft pick for the user's team. Requires explicit confirmation gate.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season", "confirmed"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "provider_id": {"type": "string", "description": "Player provider identifier (optional if full_name is provided)."},
                "full_name": {"type": "string", "description": "Player full name (optional if provider_id is provided)."},
                "position": {"type": "string", "description": "Player position."},
                "team": {"type": "string", "description": "Player NFL team."},
                "overall_pick": {"type": "integer", "description": "Overall pick number."},
                "idempotency_key": {"type": "string", "description": "Idempotency key to prevent duplicates."},
                "confirmed": {
                    "type": "boolean",
                    "description": "Human confirmation gate. Must be true to record pick.",
                },
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_record_observed_pick",
        "description": "Record an opponent draft selection to update draft sequence, advance the pick clock, and remove player from watch list.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season", "overall_pick"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "overall_pick": {"type": "integer", "description": "Overall pick number for this opponent selection."},
                "provider_id": {"type": "string", "description": "Player provider ID (optional if full_name is provided)."},
                "full_name": {"type": "string", "description": "Player full name (optional if provider_id is provided)."},
                "position": {"type": "string", "description": "Player position abbreviation."},
                "team": {"type": "string", "description": "Player NFL team abbreviation."},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_observe_pick",
        "description": "Alias for draft_record_observed_pick.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season", "overall_pick"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "overall_pick": {"type": "integer", "description": "Overall pick number for this opponent selection."},
                "provider_id": {"type": "string", "description": "Player provider ID (optional if full_name is provided)."},
                "full_name": {"type": "string", "description": "Player full name (optional if provider_id is provided)."},
                "position": {"type": "string", "description": "Player position abbreviation."},
                "team": {"type": "string", "description": "Player NFL team abbreviation."},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_next_pick_preview",
        "description": "Show the next upcoming user pick number, target positions, tiers, and availability estimates.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "draft_update_strategy",
        "description": "Update active living strategy priorities, fades, or notes during a draft session.",
        "inputSchema": {
            "type": "object",
            "required": ["league_id", "season"],
            "properties": {
                "league_id": {"type": "string", "description": "League identifier."},
                "season": {"type": "integer", "description": "NFL season year."},
                "priority_positions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Updated ordered list of priority positions (e.g., ['WR', 'RB']).",
                },
                "avoid_early": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Updated positions to avoid early (e.g., ['K', 'DEF']).",
                },
                "notes": {"type": "string", "description": "Operational notes or tactical adjustments."},
                "state_root": {"type": "string", "description": "Root state directory path.", "default": "state"},
            },
        },
    },
    {
        "name": "sleeper_get_user_drafts",
        "description": "Fetch all draft rooms for a user, season, and sport.",
        "inputSchema": {
            "type": "object",
            "required": ["user_id", "season"],
            "properties": {
                "user_id": {"type": "string", "description": "Sleeper user ID."},
                "season": {"type": "string", "description": "Season year (e.g., '2026')."},
                "sport": {"type": "string", "description": "Sport (e.g., 'nfl').", "default": "nfl"}
            }
        }
    },
    {
        "name": "sleeper_get_draft",
        "description": "Fetch the core settings of a specific draft.",
        "inputSchema": {
            "type": "object",
            "required": ["draft_id"],
            "properties": {
                "draft_id": {"type": "string", "description": "Sleeper draft ID."}
            }
        }
    },
    {
        "name": "sleeper_get_draft_picks",
        "description": "Fetch the full list of picks made in a specific draft.",
        "inputSchema": {
            "type": "object",
            "required": ["draft_id"],
            "properties": {
                "draft_id": {"type": "string", "description": "Sleeper draft ID."}
            }
        }
    },
]


def _ensure_players_state(state_root: Path, refresh: bool = False) -> dict[str, Any]:
    try:
        if not refresh:
            path = latest_snapshot(state_root)
            return {"exists": True, "fetched": False, "snapshot": str(path)}
    except FileNotFoundError:
        pass

    retrieved_at = datetime.now(timezone.utc)
    payload = fetch_players()
    path = save_snapshot(payload, state_root, retrieved_at)
    return {"exists": True, "fetched": True, "snapshot": str(path), "record_count": len(payload)}


def _ensure_trending_state(state_root: Path, refresh: bool = False) -> dict[str, Any]:
    try:
        if not refresh:
            path = latest_trending_snapshot(state_root)
            return {"exists": True, "fetched": False, "snapshot": str(path)}
    except FileNotFoundError:
        pass

    retrieved_at = datetime.now(timezone.utc)
    add_entries = fetch_trending("add")
    drop_entries = fetch_trending("drop")
    path = save_trending_snapshot(
        add_entries=add_entries,
        drop_entries=drop_entries,
        state_root=state_root,
        retrieved_at=retrieved_at,
        lookback_hours=24,
        limit=25,
    )
    return {
        "exists": True,
        "fetched": True,
        "snapshot": str(path),
        "add_count": len(add_entries),
        "drop_count": len(drop_entries),
    }


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    state_root = Path(arguments.get("state_root") or "state")

    if name == "sleeper_ensure_player_state":
        refresh = bool(arguments.get("refresh", False))
        return _ensure_players_state(state_root, refresh=refresh)

    if name == "sleeper_query_players":
        _ensure_players_state(state_root, refresh=False)
        snapshot_path = latest_snapshot(state_root)
        players = load_players(snapshot_path)
        matches = query_players(
            players,
            name=arguments.get("name"),
            position=arguments.get("position"),
            team=arguments.get("team"),
            active_only=bool(arguments.get("activeOnly", False)),
            limit=int(arguments.get("limit", 20)),
        )
        return {"count": len(matches), "players": matches, "snapshot": str(snapshot_path)}

    if name == "sleeper_query_trending_players":
        refresh = bool(arguments.get("refresh", False))
        _ensure_trending_state(state_root, refresh=refresh)
        snapshot_path = latest_trending_snapshot(state_root)
        trending = load_trending(snapshot_path)
        try:
            player_snapshot = latest_snapshot(state_root)
            players = load_players(player_snapshot)
        except FileNotFoundError:
            players = []
        matches = query_trending_players(
            trending,
            players=players,
            direction=arguments.get("direction", "add"),
            position=arguments.get("position"),
            team=arguments.get("team"),
            limit=int(arguments.get("limit", 25)),
        )
        return {
            "count": len(matches),
            "direction": arguments.get("direction", "add"),
            "players": matches,
            "snapshot": str(snapshot_path),
        }

    if name == "draft_get_session":
        loaded = load_draft_session(
            state_root, league_id=arguments["league_id"], season=int(arguments["season"])
        )
        session = loaded["session"]
        roster_summary = calculate_roster_summary(session.get("selected_players", []))
        next_pick = next_pick_for_slot(
            int(session["current_overall_pick"]),
            int(session["team_count"]),
            int(session["user_slot"]),
            reverse_round=bool(session["reverse_round"]),
        )
        return {
            "session": session,
            "living_strategy": loaded["living_strategy"],
            "roster_summary": roster_summary,
            "current_overall_pick": session["current_overall_pick"],
            "next_pick": next_pick,
            "picks_until_user_turn": next_pick["overall_pick"] - session["current_overall_pick"],
            "selected_players_count": len(session.get("selected_players", [])),
            "observed_picks_count": len(session.get("observed_picks", [])),
            "status": session.get("status"),
        }

    if name == "draft_init_session":
        allow_existing = bool(arguments.get("allow_existing", True))
        try:
            return create_draft_session(
                state_root,
                league_id=arguments["league_id"],
                season=int(arguments["season"]),
                draft_style=arguments["draft_style"],
                team_count=int(arguments["team_count"]),
                user_slot=int(arguments["user_slot"]),
                active_strategy=arguments.get("strategy_json") or {},
                active_strategy_id=arguments.get("active_strategy_id"),
                reverse_round=bool(arguments.get("reverse_round", False)),
                decision_window_seconds=int(arguments.get("decision_window_seconds", 90)),
            )
        except FileExistsError:
            if allow_existing:
                loaded = load_draft_session(
                    state_root, league_id=arguments["league_id"], season=int(arguments["season"])
                )
                return {
                    **loaded,
                    "already_existed": True,
                    "roster_summary": calculate_roster_summary(loaded["session"].get("selected_players", [])),
                }
            raise

    if name == "draft_recommend_candidates":
        candidates = arguments["candidates"]
        if not 2 <= len(candidates) <= 4:
            raise ValueError("candidates must contain between 2 and 4 candidate inputs")
        loaded = load_draft_session(state_root, league_id=arguments["league_id"], season=int(arguments["season"]))
        _ensure_players_state(state_root, refresh=False)
        players = load_players(latest_snapshot(state_root))
        try:
            trending = load_trending(latest_trending_snapshot(state_root))
        except FileNotFoundError:
            trending = None
        selected_ids = [item["provider_id"] for item in loaded["session"].get("selected_players", [])]
        observed_ids = [item["provider_id"] for item in loaded["session"].get("observed_picks", [])]
        drafted_ids = list(set(selected_ids + observed_ids))
        result = recommend_candidates(
            players,
            candidates,
            strategy=loaded["living_strategy"],
            drafted_provider_ids=drafted_ids,
            trending=trending,
            selected_players=loaded["session"].get("selected_players", []),
        )
        result["roster_summary"] = calculate_roster_summary(loaded["session"].get("selected_players", []))
        recommendation_dir = state_root / "drafts" / arguments["league_id"] / str(arguments["season"]) / "recommendations"
        recommendation_dir.mkdir(parents=True, exist_ok=True)
        recommendation_path = recommendation_dir / f"{result['generated_at'].replace(':', '-')}.json"
        recommendation_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        result["recommendation_file"] = str(recommendation_path)
        return result

    if name == "draft_record_pick":
        if not arguments.get("confirmed"):
            raise PermissionError("draft_record_pick requires explicit confirmation gate (confirmed: true)")
        _ensure_players_state(state_root, refresh=False)
        players = load_players(latest_snapshot(state_root))
        provider_id = str(arguments.get("provider_id") or "").strip()
        full_name = str(arguments.get("full_name") or "").strip()
        if not provider_id and not full_name:
            raise ValueError("Either provider_id or full_name must be provided")

        if not provider_id and full_name:
            matched = [p for p in players if p.get("full_name", "").casefold() == full_name.casefold()]
            if not matched:
                matched = [p for p in players if full_name.casefold() in p.get("full_name", "").casefold()]
            if len(matched) == 1:
                provider_id = str(matched[0]["provider_id"])
                full_name = matched[0]["full_name"]
            elif len(matched) > 1:
                raise ValueError(f"Player name '{full_name}' is ambiguous: {[p.get('full_name') for p in matched[:3]]}")
            else:
                raise ValueError(f"Player '{full_name}' not found in player snapshot")

        updated_session = record_pick(
            state_root,
            league_id=arguments["league_id"],
            season=int(arguments["season"]),
            provider_id=provider_id,
            player={
                "provider_id": provider_id,
                "full_name": full_name or None,
                "position": arguments.get("position"),
                "team": arguments.get("team"),
            },
            confirmed=True,
            idempotency_key=arguments.get("idempotency_key"),
            overall_pick=arguments.get("overall_pick"),
            all_players=players,
        )
        roster_summary = calculate_roster_summary(updated_session.get("selected_players", []))
        next_pick = next_pick_for_slot(
            int(updated_session["current_overall_pick"]),
            int(updated_session["team_count"]),
            int(updated_session["user_slot"]),
            reverse_round=bool(updated_session["reverse_round"]),
        )
        return {
            "session": updated_session,
            "roster_summary": roster_summary,
            "next_pick": next_pick,
            "picks_until_user_turn": next_pick["overall_pick"] - updated_session["current_overall_pick"],
        }

    if name in ("draft_record_observed_pick", "draft_observe_pick"):
        _ensure_players_state(state_root, refresh=False)
        players = load_players(latest_snapshot(state_root))
        provider_id = str(arguments.get("provider_id") or "").strip()
        full_name = str(arguments.get("full_name") or "").strip()
        overall_pick = int(arguments["overall_pick"])
        if not provider_id and not full_name:
            raise ValueError("Either provider_id or full_name must be provided")

        if not provider_id and full_name:
            matched = [p for p in players if p.get("full_name", "").casefold() == full_name.casefold()]
            if not matched:
                matched = [p for p in players if full_name.casefold() in p.get("full_name", "").casefold()]
            if len(matched) == 1:
                provider_id = str(matched[0]["provider_id"])
                full_name = matched[0]["full_name"]
            elif len(matched) > 1:
                raise ValueError(f"Player name '{full_name}' is ambiguous: {[p.get('full_name') for p in matched[:3]]}")
            else:
                provider_id = f"obs-{overall_pick}"

        updated_session = record_observed_pick(
            state_root,
            league_id=arguments["league_id"],
            season=int(arguments["season"]),
            provider_id=provider_id,
            player={
                "full_name": full_name or None,
                "position": arguments.get("position"),
                "team": arguments.get("team"),
            },
            overall_pick=overall_pick,
            all_players=players,
        )
        next_pick = next_pick_for_slot(
            int(updated_session["current_overall_pick"]),
            int(updated_session["team_count"]),
            int(updated_session["user_slot"]),
            reverse_round=bool(updated_session["reverse_round"]),
        )
        return {
            "current_overall_pick": updated_session["current_overall_pick"],
            "observed_picks_count": len(updated_session.get("observed_picks", [])),
            "next_pick": next_pick,
            "picks_until_user_turn": next_pick["overall_pick"] - updated_session["current_overall_pick"],
        }

    if name == "draft_next_pick_preview":
        _ensure_players_state(state_root, refresh=False)
        players = load_players(latest_snapshot(state_root))
        try:
            trending = load_trending(latest_trending_snapshot(state_root))
        except FileNotFoundError:
            trending = None
        preview = next_pick_preview(
            state_root,
            league_id=arguments["league_id"],
            season=int(arguments["season"]),
            players=players,
            trending=trending,
        )
        loaded = load_draft_session(state_root, league_id=arguments["league_id"], season=int(arguments["season"]))
        preview["roster_summary"] = calculate_roster_summary(loaded["session"].get("selected_players", []))
        return preview

    if name == "draft_update_strategy":
        return update_living_strategy(
            state_root,
            league_id=arguments["league_id"],
            season=int(arguments["season"]),
            priority_positions=arguments.get("priority_positions"),
            avoid_early=arguments.get("avoid_early"),
            notes=arguments.get("notes"),
        )

    if name == "sleeper_get_user_drafts":
        user_id = arguments["user_id"]
        season = arguments["season"]
        sport = arguments.get("sport", "nfl")
        url = f"https://api.sleeper.app/v1/user/{user_id}/drafts/{sport}/{season}"
        return {"drafts": _sleeper_api_get(url)}

    if name == "sleeper_get_draft":
        draft_id = arguments["draft_id"]
        url = f"https://api.sleeper.app/v1/draft/{draft_id}"
        return _sleeper_api_get(url)

    if name == "sleeper_get_draft_picks":
        draft_id = arguments["draft_id"]
        url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
        return {"picks": _sleeper_api_get(url)}

    raise ValueError(f"Unknown tool: {name}")


def handle_message(message: dict[str, Any]) -> dict[str, Any] | None:
    msg_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = execute_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, sort_keys=True)}],
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error: {exc}"}],
                    "isError": True,
                },
            }

    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    return None


def run_stdio_server(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
            continue

        response = handle_message(message)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


def main() -> int:
    run_stdio_server()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
