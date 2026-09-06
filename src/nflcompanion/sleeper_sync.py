"""Real-time draft synchronization engine for Sleeper drafts."""

from __future__ import annotations

import json
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from nflcompanion.draft_companion import (
    load_draft_session,
    record_observed_pick,
)

SLEEPER_DRAFT_PICKS_URL = "https://api.sleeper.app/v1/draft/{draft_id}/picks"
SLEEPER_DRAFT_URL = "https://api.sleeper.app/v1/draft/{draft_id}"


def fetch_sleeper_draft_picks(draft_id: str, *, timeout: int = 15) -> list[dict[str, Any]]:
    """Fetch live picks from Sleeper REST API."""
    url = SLEEPER_DRAFT_PICKS_URL.format(draft_id=draft_id)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise ValueError(f"Expected list of picks from Sleeper API, got {type(payload).__name__}")
    return payload


def fetch_sleeper_draft_status(draft_id: str, *, timeout: int = 15) -> dict[str, Any]:
    """Fetch draft status and metadata from Sleeper REST API."""
    url = SLEEPER_DRAFT_URL.format(draft_id=draft_id)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict from Sleeper API, got {type(payload).__name__}")
    return payload


def sync_sleeper_draft_picks(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    draft_id: str,
    players: Iterable[dict[str, Any]] | None = None,
    raw_picks: list[dict[str, Any]] | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """Synchronize live picks from Sleeper draft into local draft session.

    Identifies newly drafted players by opponents and appends them as observed picks,
    eliminating them from future recommendations and watchlists.
    If raw_picks is provided, uses them directly (for testing and offline playback).
    """
    loaded = load_draft_session(state_root, league_id=league_id, season=season)
    session = loaded["session"]
    user_slot = int(session.get("user_slot", 0))

    if raw_picks is None:
        raw_picks = fetch_sleeper_draft_picks(draft_id, timeout=timeout)

    existing_selected_ids = {
        str(item.get("provider_id")) for item in session.get("selected_players", [])
    }
    existing_observed_ids = {
        str(item.get("provider_id")) for item in session.get("observed_picks", [])
    }
    existing_overall_picks = {
        int(item["overall_pick"])
        for item in session.get("selected_players", []) + session.get("observed_picks", [])
        if item.get("overall_pick") is not None
    }

    player_by_id: dict[str, dict[str, Any]] = {}
    if players:
        for p in players:
            pid = str(p.get("provider_id") or p.get("player_id") or "")
            if pid:
                player_by_id[pid] = p

    newly_observed: list[dict[str, Any]] = []
    user_picks_detected: list[dict[str, Any]] = []

    sorted_picks = sorted(raw_picks, key=lambda p: int(p.get("pick_no", 0)))

    for pick in sorted_picks:
        pick_no = int(pick.get("pick_no", 0))
        player_id = str(pick.get("player_id") or "")
        draft_slot = int(pick.get("draft_slot", 0))
        metadata = pick.get("metadata") or {}

        if not player_id:
            continue

        if (
            player_id in existing_selected_ids
            or player_id in existing_observed_ids
            or pick_no in existing_overall_picks
        ):
            continue

        local_player = player_by_id.get(player_id)
        if local_player:
            full_name = local_player.get("full_name") or f"{metadata.get('first_name', '')} {metadata.get('last_name', '')}".strip()
            position = local_player.get("position") or metadata.get("position")
            team = local_player.get("team") or metadata.get("team")
        else:
            first = metadata.get("first_name", "")
            last = metadata.get("last_name", "")
            full_name = f"{first} {last}".strip() or player_id
            position = metadata.get("position")
            team = metadata.get("team")

        if draft_slot == user_slot:
            user_picks_detected.append(
                {
                    "overall_pick": pick_no,
                    "provider_id": player_id,
                    "full_name": full_name,
                    "position": position,
                    "team": team,
                    "round": pick.get("round"),
                    "slot": draft_slot,
                }
            )
        else:
            session = record_observed_pick(
                state_root,
                league_id=league_id,
                season=season,
                provider_id=player_id,
                player={
                    "full_name": full_name,
                    "position": position,
                    "team": team,
                },
                overall_pick=pick_no,
                all_players=players,
            )
            existing_observed_ids.add(player_id)
            existing_overall_picks.add(pick_no)
            newly_observed.append(
                {
                    "overall_pick": pick_no,
                    "provider_id": player_id,
                    "full_name": full_name,
                    "position": position,
                    "team": team,
                }
            )

    return {
        "league_id": league_id,
        "season": season,
        "draft_id": draft_id,
        "total_picks_in_sleeper": len(sorted_picks),
        "newly_observed_picks": newly_observed,
        "user_picks_detected": user_picks_detected,
        "current_overall_pick": session.get("current_overall_pick", 0),
        "total_observed": len(session.get("observed_picks", [])),
        "total_selected": len(session.get("selected_players", [])),
    }
