"""Draft-session state, snake-draft math, and deterministic recommendations."""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST", "DEF"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _session_dir(state_root: Path, league_id: str, season: int) -> Path:
    return state_root / "drafts" / str(league_id) / str(season)


def _json_front_matter(payload: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in payload.items():
        lines.append(f"{key}: {json.dumps(value, sort_keys=True, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines)


def _read_front_matter(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} must start with JSON front matter")
    payload: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return payload
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        payload[key] = json.loads(value)
    raise ValueError(f"{path} has unterminated front matter")


def _write_session_markdown(path: Path, session: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "\n\n# Draft session\n\n"
        "This file is the human-readable session state. Confirmed picks are "
        "recorded in `events.md`; the working plan is in `living-strategy.md`.\n"
    )
    path.write_text(_json_front_matter(session) + body, encoding="utf-8")


def _load_session(state_root: Path, league_id: str, season: int) -> dict[str, Any]:
    return _read_front_matter(_session_dir(state_root, league_id, season) / "session.md")


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _positions(player: dict[str, Any]) -> set[str]:
    values = player.get("fantasy_positions") or []
    result = {str(value).upper() for value in values if value}
    if player.get("position"):
        result.add(str(player["position"]).upper())
    return result


# Default minimum requirements per draft style
_ROSTER_MINIMUMS: dict[str, dict[str, int]] = {
    "espn_snake": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 5, "DEF": 1, "K": 1},
    "sleeper_dynasty": {"QB": 2, "RB": 2, "WR": 3, "TE": 1, "FLEX": 10},
}
_ROSTER_FLEX_KEY = "FLEX"


def calculate_roster_summary(
    selected_players: list[dict[str, Any]],
    *,
    target_roster_size: int | None = None,
    draft_style: str = "espn_snake",
) -> dict[str, Any]:
    """Calculate roster composition, positional counts, and remaining needs.

    For ``sleeper_dynasty`` the target roster size defaults to 25 (active spots)
    and DEF/K are not counted as positional needs. For ``espn_snake`` the default
    remains 14 with DEF and K required.
    """
    is_dynasty = draft_style == "sleeper_dynasty"
    if target_roster_size is None:
        target_roster_size = 25 if is_dynasty else 14

    minimums = _ROSTER_MINIMUMS.get(draft_style, _ROSTER_MINIMUMS["espn_snake"])

    track_positions = ["QB", "RB", "WR", "TE", "DEF", "K"]
    counts: dict[str, int] = {pos: 0 for pos in track_positions}
    by_position: dict[str, list[dict[str, Any]]] = {pos: [] for pos in track_positions}
    by_position["OTHER"] = []

    for item in selected_players:
        pos = str(item.get("position") or "").upper()
        if pos in ("DST", "DEF", "D/ST"):
            pos = "DEF"
        if pos in counts:
            counts[pos] += 1
            by_position[pos].append(item)
        else:
            by_position["OTHER"].append(item)

    needs: list[str] = []
    flex_total = counts["RB"] + counts["WR"] + counts["TE"]

    qb_min = minimums.get("QB", 1)
    if counts["QB"] < qb_min:
        label = "QB" if qb_min == 1 else f"QB ({qb_min - counts['QB']} needed for Superflex)"
        needs.append(label)

    rb_min = minimums.get("RB", 2)
    if counts["RB"] < rb_min:
        needs.append(f"RB ({rb_min - counts['RB']} needed)")

    wr_min = minimums.get("WR", 2)
    if counts["WR"] < wr_min:
        needs.append(f"WR ({wr_min - counts['WR']} needed)")

    if counts["TE"] < minimums.get("TE", 1):
        needs.append("TE")

    flex_min = minimums.get("FLEX", 5)
    if flex_total < flex_min:
        flex_label = "FLEX (RB/WR/TE)" if not is_dynasty else "FLEX/Superflex (RB/WR/TE/QB)"
        needs.append(flex_label)

    if not is_dynasty:
        if counts["DEF"] < minimums.get("DEF", 1):
            needs.append("DEF")
        if counts["K"] < minimums.get("K", 1):
            needs.append("K")

    total_selected = len(selected_players)
    remaining_slots = max(0, target_roster_size - total_selected)

    return {
        "total_selected": total_selected,
        "target_roster_size": target_roster_size,
        "remaining_slots": remaining_slots,
        "position_counts": counts,
        "by_position": by_position,
        "needs": needs,
    }


def pick_for_overall(
    overall_pick: int,
    team_count: int,
    *,
    reverse_round: bool = False,
) -> dict[str, int]:
    """Return round and draft slot for a one-based overall pick."""
    if overall_pick < 1:
        raise ValueError("overall_pick must be positive")
    if team_count < 2:
        raise ValueError("team_count must be at least 2")
    round_number = (overall_pick - 1) // team_count + 1
    offset = (overall_pick - 1) % team_count
    forward = round_number % 2 == 1
    if reverse_round and round_number >= 3:
        forward = round_number % 2 == 0
    slot = offset + 1 if forward else team_count - offset
    return {"overall_pick": overall_pick, "round": round_number, "slot": slot}


def next_pick_for_slot(
    current_overall_pick: int,
    team_count: int,
    user_slot: int,
    *,
    reverse_round: bool = False,
) -> dict[str, int]:
    """Find the next pick for a user's draft slot after the current pick."""
    if user_slot < 1 or user_slot > team_count:
        raise ValueError("user_slot must be within the team count")
    if current_overall_pick < 0:
        raise ValueError("current_overall_pick cannot be negative")
    overall_pick = current_overall_pick + 1
    while pick_for_overall(
        overall_pick, team_count, reverse_round=reverse_round
    )["slot"] != user_slot:
        overall_pick += 1
    return pick_for_overall(overall_pick, team_count, reverse_round=reverse_round)


def create_draft_session(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    draft_style: str,
    team_count: int,
    user_slot: int,
    active_strategy: dict[str, Any] | None = None,
    active_strategy_id: str | None = None,
    reverse_round: bool = False,
    decision_window_seconds: int = 90,
) -> dict[str, Any]:
    """Create the durable session and its initial living strategy.

    Pass ``user_slot=0`` when the draft position is not yet known (e.g. during
    strategy creation before the actual draft). The session records
    ``draft_slot_status: "TBD"`` and skips pick-number math until the slot is
    confirmed via :func:`confirm_draft_slot`.
    """
    if decision_window_seconds <= 0:
        raise ValueError("decision_window_seconds must be positive")
    pick_for_overall(1, team_count, reverse_round=reverse_round)
    slot_known = user_slot != 0
    if slot_known and (user_slot < 1 or user_slot > team_count):
        raise ValueError("user_slot must be within the team count or 0 for TBD")
    directory = _session_dir(state_root, league_id, season)
    session_path = directory / "session.md"
    if session_path.exists():
        raise FileExistsError(f"Draft session already exists: {session_path}")
    created_at = _now()
    strategy = deepcopy(active_strategy or {})
    session = {
        "session_id": f"{league_id}-{season}",
        "league_id": str(league_id),
        "season": int(season),
        "draft_style": draft_style,
        "team_count": int(team_count),
        "user_slot": int(user_slot),
        "draft_slot_status": "confirmed" if slot_known else "TBD",
        "current_overall_pick": 0,
        "reverse_round": bool(reverse_round),
        "decision_window_seconds": int(decision_window_seconds),
        "active_strategy_id": active_strategy_id,
        "status": "planned",
        "created_at": created_at,
        "updated_at": created_at,
        "selected_players": [],
        "observed_picks": [],
    }
    directory.mkdir(parents=True, exist_ok=True)
    _write_session_markdown(session_path, session)
    (directory / "events.md").write_text("# Draft events\n", encoding="utf-8")
    _write_living_strategy(directory / "living-strategy.md", session, strategy, [])
    return {"session": deepcopy(session), "living_strategy": strategy}


def confirm_draft_slot(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    user_slot: int,
) -> dict[str, Any]:
    """Update a TBD session with the confirmed draft slot.

    Call this at the start of the actual draft once the slot is revealed by the
    platform. Raises :exc:`ValueError` if the session already has a confirmed slot.
    """
    directory = _session_dir(state_root, league_id, season)
    session_path = directory / "session.md"
    session = _read_front_matter(session_path)
    team_count = int(session.get("team_count", 0))
    if team_count < 2:
        raise ValueError("Session team_count is missing or invalid")
    if user_slot < 1 or user_slot > team_count:
        raise ValueError("user_slot must be within the team count")
    if session.get("draft_slot_status") == "confirmed" and session.get("user_slot", 0) != 0:
        raise ValueError(
            f"Draft slot is already confirmed as slot {session['user_slot']}; "
            "create a new session or reset the existing one."
        )
    session["user_slot"] = int(user_slot)
    session["draft_slot_status"] = "confirmed"
    session["updated_at"] = _now()
    _write_session_markdown(session_path, session)
    return deepcopy(session)


def load_draft_session(state_root: Path, *, league_id: str, season: int) -> dict[str, Any]:
    """Load session metadata and the current living strategy."""
    directory = _session_dir(state_root, league_id, season)
    session = _load_session(state_root, league_id, season)
    strategy = _read_front_matter(directory / "living-strategy.md")
    return {"session": session, "living_strategy": strategy}


def resolve_candidates(
    players: Iterable[dict[str, Any]], candidate_inputs: Iterable[str]
) -> dict[str, Any]:
    """Resolve surname-like inputs without silently choosing ambiguous players."""
    inputs = [str(value).strip() for value in candidate_inputs if str(value).strip()]
    if not 2 <= len(inputs) <= 4:
        raise ValueError("candidate_inputs must contain between 2 and 4 players")
    normalized_players = list(players)
    resolved: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for raw_input in inputs:
        parts = raw_input.split()
        requested_position = next(
            (part.upper() for part in parts if part.upper() in _POSITIONS), None
        )
        name_parts = [part for part in parts if part.upper() not in _POSITIONS]
        query = _normalize(" ".join(name_parts or parts))
        matches = []
        for player in normalized_players:
            full_name = str(player.get("full_name") or "")
            normalized_name = _normalize(full_name)
            surname = _normalize(full_name.split()[-1]) if full_name else ""
            if query not in {normalized_name, surname} and query not in normalized_name:
                continue
            if requested_position and requested_position not in _positions(player):
                continue
            matches.append(player)
        unique_matches = {str(player.get("provider_id")): player for player in matches}
        matches = list(unique_matches.values())
        if len(matches) == 1:
            player = deepcopy(matches[0])
            provider_id = str(player.get("provider_id"))
            if provider_id not in seen:
                seen.add(provider_id)
                resolved.append(player)
        elif len(matches) > 1:
            ambiguous.append(
                {
                    "input": raw_input,
                    "matches": [
                        {
                            "provider_id": str(player.get("provider_id")),
                            "full_name": player.get("full_name"),
                            "position": player.get("position"),
                            "team": player.get("team"),
                        }
                        for player in matches
                    ],
                }
            )
        else:
            unknown.append(raw_input)
    return {"resolved": resolved, "ambiguous": ambiguous, "unknown": unknown}


def recommend_candidates(
    players: Iterable[dict[str, Any]],
    candidate_inputs: Iterable[str],
    *,
    strategy: dict[str, Any] | None = None,
    drafted_provider_ids: Iterable[str] = (),
    trending: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve and deterministically rank 2-4 candidate inputs."""
    strategy = strategy or {}
    resolution = resolve_candidates(players, candidate_inputs)
    drafted = {str(value) for value in drafted_provider_ids}
    trend_counts: dict[str, int] = {}
    if trending:
        for entry in trending.get("add", []):
            if isinstance(entry, dict) and entry.get("player_id") is not None:
                trend_counts[str(entry["player_id"])] = int(entry.get("count") or 0)
    priorities = [
        str(value).upper()
        for value in strategy.get("priority_positions", strategy.get("priorities", []))
    ]
    avoided = {str(value).upper() for value in strategy.get("avoid_early", [])}
    recommendations = []
    for player in resolution["resolved"]:
        provider_id = str(player.get("provider_id"))
        if provider_id in drafted:
            continue
        player_positions = _positions(player)
        position = str(player.get("position") or next(iter(player_positions), "")).upper()
        need = 30 if position in priorities else 12
        strategy_fit = 25 if position in priorities else 8
        if position in avoided:
            strategy_fit -= 25
        search_rank = player.get("search_rank")
        value = 20 if isinstance(search_rank, (int, float)) and search_rank <= 50 else 10
        activity = min(10, trend_counts.get(provider_id, 0) // 100)
        active = 10 if player.get("active", True) else -20
        factors = {
            "positional_need": need,
            "strategy_fit": strategy_fit,
            "available_value": value,
            "trend_signal": activity,
            "active_status": active,
        }
        score = sum(factors.values())
        reasons = []
        if position in priorities:
            reasons.append(f"fits the {position} priority")
        else:
            reasons.append(f"adds {position} value outside the current priority")
        if activity:
            reasons.append("has a positive local trend signal")
        if position in avoided:
            reasons.append(f"conflicts with the early {position} fade")
        recommendations.append(
            {
                "provider_id": provider_id,
                "full_name": player.get("full_name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "score": score,
                "factor_scores": factors,
                "confidence": "high" if search_rank is not None else "medium",
                "rationale": "; ".join(reasons).capitalize() + ".",
            }
        )
    recommendations.sort(key=lambda item: (-item["score"], item["full_name"] or ""))
    for index, recommendation in enumerate(recommendations, start=1):
        recommendation["rank"] = index
    return {
        "resolved": resolution["resolved"],
        "ambiguous": resolution["ambiguous"],
        "unknown": resolution["unknown"],
        "recommendations": recommendations,
        "generated_at": _now(),
    }


def _append_event(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("{"):
            events.append(json.loads(line))
    return events


def _write_living_strategy(
    path: Path, session: dict[str, Any], strategy: dict[str, Any], events: list[dict[str, Any]]
) -> None:
    payload = deepcopy(strategy)
    payload["session_id"] = session["session_id"]
    payload["selected_players"] = deepcopy(session["selected_players"])
    payload["current_overall_pick"] = session["current_overall_pick"]
    payload["updated_at"] = session["updated_at"]
    payload["confirmed_pick_count"] = sum(event.get("event") == "pick_confirmed" for event in events)
    path.write_text(
        _json_front_matter(payload)
        + "\n\n# Living strategy\n\n"
        "This working strategy is derived from the selected baseline and confirmed events.\n",
        encoding="utf-8",
    )


def record_pick(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    provider_id: str,
    player: dict[str, Any] | None = None,
    confirmed: bool,
    idempotency_key: str | None = None,
    overall_pick: int | None = None,
    all_players: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Append a confirmed user pick and update the session projection."""
    if not confirmed:
        raise PermissionError("A pick must be explicitly confirmed before recording")
    loaded = load_draft_session(state_root, league_id=league_id, season=season)
    session = loaded["session"]
    directory = _session_dir(state_root, league_id, season)
    events_path = directory / "events.md"
    events = _read_events(events_path)
    key = idempotency_key or str(uuid.uuid4())
    if any(event.get("idempotency_key") == key for event in events):
        return deepcopy(session)
    selected_ids = {str(item.get("provider_id")) for item in session["selected_players"]}
    if str(provider_id) in selected_ids:
        raise ValueError(f"Player {provider_id} has already been selected by the user")

    player_info = deepcopy(player or {})
    if all_players and (not player_info.get("full_name") or not player_info.get("position")):
        for p in all_players:
            if str(p.get("provider_id")) == str(provider_id):
                for k in ("full_name", "position", "team"):
                    if not player_info.get(k) and p.get(k):
                        player_info[k] = p[k]
                break

    pick = overall_pick or int(session["current_overall_pick"]) + 1
    pick_details = pick_for_overall(
        pick, int(session["team_count"]), reverse_round=bool(session["reverse_round"])
    )
    selected = {
        "provider_id": str(provider_id),
        "full_name": player_info.get("full_name"),
        "position": player_info.get("position"),
        "team": player_info.get("team"),
        "overall_pick": pick,
        "round": pick_details["round"],
        "slot": pick_details["slot"],
    }
    event = {
        "event": "pick_confirmed",
        "event_id": str(uuid.uuid4()),
        "idempotency_key": key,
        "created_at": _now(),
        "league_id": str(league_id),
        "season": int(season),
        "player": selected,
        "source": "user",
    }
    _append_event(events_path, event)
    session["selected_players"].append(selected)
    session["current_overall_pick"] = pick
    session["status"] = "active"
    session["updated_at"] = event["created_at"]
    _write_session_markdown(directory / "session.md", session)
    _write_living_strategy(directory / "living-strategy.md", session, loaded["living_strategy"], events + [event])
    return deepcopy(session)


def record_observed_pick(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    provider_id: str,
    player: dict[str, Any] | None = None,
    overall_pick: int,
    all_players: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Append an opponent pick without adding it to the user's roster."""
    loaded = load_draft_session(state_root, league_id=league_id, season=season)
    session = loaded["session"]
    directory = _session_dir(state_root, league_id, season)
    events = _read_events(directory / "events.md")

    player_info = deepcopy(player or {})
    if all_players and (not player_info.get("full_name") or not player_info.get("position")):
        for p in all_players:
            if str(p.get("provider_id")) == str(provider_id):
                for k in ("full_name", "position", "team"):
                    if not player_info.get(k) and p.get(k):
                        player_info[k] = p[k]
                break

    details = pick_for_overall(overall_pick, session["team_count"], reverse_round=session["reverse_round"])
    event = {
        "event": "pick_observed",
        "event_id": str(uuid.uuid4()),
        "created_at": _now(),
        "league_id": str(league_id),
        "season": int(season),
        "player": {**player_info, "provider_id": str(provider_id), **details},
        "source": "import",
    }
    _append_event(directory / "events.md", event)
    session["current_overall_pick"] = max(int(session["current_overall_pick"]), overall_pick)
    session["observed_picks"].append(event["player"])
    session["updated_at"] = event["created_at"]
    _write_session_markdown(directory / "session.md", session)
    _write_living_strategy(directory / "living-strategy.md", session, loaded["living_strategy"], events + [event])
    return deepcopy(session)


def update_living_strategy(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    priority_positions: list[str] | None = None,
    avoid_early: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update working draft priorities or notes in living-strategy.md."""
    loaded = load_draft_session(state_root, league_id=league_id, season=season)
    session = loaded["session"]
    strategy = loaded["living_strategy"]
    directory = _session_dir(state_root, league_id, season)
    events = _read_events(directory / "events.md")

    if priority_positions is not None:
        strategy["priority_positions"] = [str(p).upper() for p in priority_positions]
    if avoid_early is not None:
        strategy["avoid_early"] = [str(p).upper() for p in avoid_early]
    if notes is not None:
        strategy["notes"] = str(notes)
    strategy["updated_at"] = _now()

    _write_living_strategy(directory / "living-strategy.md", session, strategy, events)
    return deepcopy(strategy)



def next_pick_preview(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    players: Iterable[dict[str, Any]] | None = None,
    trending: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the next user pick and a local trend-backed watch list."""
    loaded = load_draft_session(state_root, league_id=league_id, season=season)
    session = loaded["session"]
    next_pick = next_pick_for_slot(
        int(session["current_overall_pick"]),
        int(session["team_count"]),
        int(session["user_slot"]),
        reverse_round=bool(session["reverse_round"]),
    )
    strategy = loaded["living_strategy"]
    priorities = [
        str(value).upper()
        for value in strategy.get("priority_positions", strategy.get("priorities", []))
    ]
    drafted_ids = {
        str(item.get("provider_id"))
        for item in session.get("selected_players", []) + session.get("observed_picks", [])
    }
    trend_counts: dict[str, int] = {}
    for entry in (trending or {}).get("add", []):
        if isinstance(entry, dict) and entry.get("player_id") is not None:
            trend_counts[str(entry["player_id"])] = int(entry.get("count") or 0)
    watch_list = []
    for player in players or []:
        provider_id = str(player.get("provider_id"))
        if provider_id in drafted_ids or not player.get("active", True):
            continue
        player_positions = _positions(player)
        position = str(player.get("position") or next(iter(player_positions), "")).upper()
        priority_index = priorities.index(position) if position in priorities else len(priorities)
        search_rank = player.get("search_rank")
        value_score = max(0, 30 - int(search_rank) // 10) if isinstance(search_rank, (int, float)) else 10
        trend_score = min(10, trend_counts.get(provider_id, 0) // 100)
        watch_score = max(0, 40 - priority_index * 8) + value_score + trend_score
        if isinstance(search_rank, (int, float)):
            availability = "borderline" if search_rank <= next_pick["overall_pick"] + session["team_count"] else "likely"
        else:
            availability = "unknown"
        watch_list.append(
            {
                "provider_id": provider_id,
                "full_name": player.get("full_name"),
                "position": player.get("position"),
                "team": player.get("team"),
                "tier_priority": priority_index + 1 if position in priorities else None,
                "trend_count": trend_counts.get(provider_id, 0),
                "availability_estimate": availability,
                "watch_score": watch_score,
            }
        )
    watch_list.sort(key=lambda item: (-item["watch_score"], item["full_name"] or ""))
    return {
        "next_pick": next_pick,
        "picks_until_user_turn": next_pick["overall_pick"] - session["current_overall_pick"],
        "recommended_positions": priorities,
        "watch_list": watch_list[:12],
        "availability_basis": "local player search rank and trending add snapshot; estimate only",
        "living_strategy": loaded["living_strategy"],
    }


__all__ = [
    "calculate_roster_summary",
    "create_draft_session",
    "load_draft_session",
    "next_pick_for_slot",
    "next_pick_preview",
    "pick_for_overall",
    "record_observed_pick",
    "record_pick",
    "recommend_candidates",
    "resolve_candidates",
    "update_living_strategy",
]

