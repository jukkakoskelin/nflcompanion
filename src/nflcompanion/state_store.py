"""Read-only access to the draft companion's durable state files."""

from __future__ import annotations

import json
import random
import re
from collections import deque
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


SUPPORTED_DRAFT_STYLES = {
    "sleeper_dynasty": {
        "platform": "sleeper",
        "draft_type": "dynasty",
        "supports_reverse_round": False,
        "context_bucket": "sleeper_dynasty",
        "default_teams": 10,
        "context_files": (
            "draft-context/sleeper_dynasty/Sleeper_league_settings.md",
            "draft-context/sleeper_dynasty/Sleeper_scoring.md",
        ),
    },
    "espn_snake": {
        "platform": "espn",
        "draft_type": "snake",
        "supports_reverse_round": True,
        "context_bucket": "espn_snake",
        "default_teams": 16,
        "context_files": ("draft-context/espn_snake/opfg_espn_2026_settings.pdf",),
    },
}
_MISSING = object()
_EARLY_ROUND_RED_FLAGS = {"K", "DST"}
_DEFAULT_AGENT_ROLES = {
    "interviewer": "draft-strategy-interviewer",
    "validator": "draft-strategy-validator",
    "writer": "draft-strategy-writer",
}
_SIMULATED_STRATEGIES = {
    "sleeper_dynasty": [
        {
            "name": "WR Anchor",
            "questionnaire": [
                {"question": "Preferred roster foundation", "answer": "Start WR-heavy with insulated dynasty assets."},
                {"question": "Quarterback timing", "answer": "Take a top-10 young QB only if value survives into rounds 3-5."},
                {"question": "Early-round avoid list", "answer": "Avoid kicker and defense until the final rounds."},
                {"question": "Mock-draft focus", "answer": "Track whether anchor WR builds still leave RB2 paths open after round 6."},
            ],
            "strategy": {
                "summary": "Open with elite WR volume, then pivot into value RBs and young QB insulation.",
                "priority_positions": ["WR", "RB", "QB"],
                "avoid_early": ["K", "DST"],
                "round_plan": [
                    {"rounds": "1-3", "targets": ["WR", "WR", "RB"], "focus": "Bank elite target share before the RB dead zone."},
                    {"rounds": "4-7", "targets": ["RB", "QB", "TE"], "focus": "Take insulated upside and weekly-starter stability."},
                    {"rounds": "8+", "targets": ["RB", "WR"], "focus": "Chase contingent value, youth, and stackable depth."},
                ],
                "notes": [
                    "Favor wide receivers with locked-in route share and multi-year security.",
                    "Pivot to value RBs when the room starts chasing uncertain WR3 profiles.",
                ],
                "mock_draft_review": [
                    "Did the anchor WR build still produce two startable RBs by round 8?",
                    "Were late QB/TE pivots available after the WR-heavy start?",
                ],
            },
        },
        {
            "name": "Balanced Youth Core",
            "questionnaire": [
                {"question": "Roster construction goal", "answer": "Blend young RB/WR starters without overcommitting to one lane."},
                {"question": "Risk tolerance", "answer": "Moderate risk with weekly floor in the first five rounds."},
                {"question": "Early-round avoid list", "answer": "No kicker or defense before the closing rounds."},
            ],
            "strategy": {
                "summary": "Alternate RB and WR value early while preserving optionality for QB/TE tiers.",
                "priority_positions": ["RB", "WR", "QB"],
                "avoid_early": ["K", "DST"],
                "round_plan": [
                    {"rounds": "1-2", "targets": ["RB", "WR"], "focus": "Take best insulated talent regardless of position."},
                    {"rounds": "3-5", "targets": ["WR", "RB", "QB"], "focus": "Stay flexible around falling elite tiers."},
                    {"rounds": "6+", "targets": ["TE", "WR", "RB"], "focus": "Finish core starters, then stack youth upside."},
                ],
                "notes": [
                    "Use trending add/drop movement as a tiebreaker only after talent and role.",
                ],
            },
        },
    ],
    "espn_snake": [
        {
            "name": "Third-Round Reversal WR Anchor",
            "reverse_round": True,
            "questionnaire": [
                {"question": "Opening preference", "answer": "Use the long wheel created by third-round reversal to lock WR value early."},
                {"question": "Quarterback timing", "answer": "Wait on QB unless a clear elite option falls past ADP."},
                {"question": "Early-round avoid list", "answer": "No kicker or defense before the final two rounds."},
            ],
            "strategy": {
                "summary": "Use the 16-team 3RR format to secure reliable WR scoring and absorb positional runs.",
                "priority_positions": ["WR", "RB", "QB"],
                "avoid_early": ["K", "DST"],
                "round_plan": [
                    {"rounds": "1-3", "targets": ["WR", "WR", "RB"], "focus": "Leverage the long return between picks with stable WR starters."},
                    {"rounds": "4-6", "targets": ["RB", "QB", "TE"], "focus": "Catch scarce onesie positions if the room lets them slide."},
                    {"rounds": "7+", "targets": ["WR", "RB"], "focus": "Build weekly flex stability for a deep league."},
                ],
                "notes": [
                    "Third-round reversal increases the penalty for risky round-2 bets; prefer stable volume.",
                ],
            },
        },
        {
            "name": "Hero RB with Late QB",
            "reverse_round": False,
            "questionnaire": [
                {"question": "Opening preference", "answer": "Secure one anchor RB, then flood WR and flex depth."},
                {"question": "League adjustment", "answer": "Treat a 16-team room as a scarcity problem, especially at WR3/flex."},
                {"question": "Early-round avoid list", "answer": "Kicker and defense stay off the board until the endgame."},
            ],
            "strategy": {
                "summary": "Grab one workload RB, then address WR depth before returning to quarterback.",
                "priority_positions": ["RB", "WR", "TE"],
                "avoid_early": ["K", "DST"],
                "round_plan": [
                    {"rounds": "1-2", "targets": ["RB", "WR"], "focus": "Leave the turn with one foundation RB and one reliable WR."},
                    {"rounds": "3-6", "targets": ["WR", "WR", "TE"], "focus": "Exploit WR scarcity before the room strips the shelf."},
                    {"rounds": "7+", "targets": ["QB", "WR", "RB"], "focus": "Backfill QB and add contingent depth."},
                ],
            },
        },
    ],
}


def _strategies_path(state_root: Path) -> Path:
    return state_root / "strategies" / "strategies.json"


def _workspace_root(state_root: Path) -> Path:
    return state_root.parent if state_root.name == "state" else state_root


def _draft_context_root(state_root: Path, draft_style: str) -> Path:
    style = SUPPORTED_DRAFT_STYLES[draft_style]
    return _workspace_root(state_root) / "draft-context" / str(style["context_bucket"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "strategy"


def _strategy_markdown_path(state_root: Path, draft_style: str, strategy_id: str, name: str) -> Path:
    return _draft_context_root(state_root, draft_style) / "strategies" / f"{strategy_id}-{_slugify(name)}.md"


def _strategy_log_path(state_root: Path, draft_style: str) -> Path:
    return _draft_context_root(state_root, draft_style) / "logs" / "strategy-creation-log.jsonl"


def _serialize_front_matter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    lines.append("---")
    return "\n".join(lines)


def _parse_front_matter(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    metadata: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ": " not in line:
            continue
        key, raw_value = line.split(": ", 1)
        try:
            metadata[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            metadata[key] = raw_value
    return metadata


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")


def _render_questionnaire(questionnaire: list[dict[str, Any]]) -> str:
    if not questionnaire:
        return "No questionnaire transcript was captured.\n"
    lines = []
    for item in questionnaire:
        lines.append(f"- Q: {item.get('question', '')}")
        lines.append(f"  A: {item.get('answer', '')}")
    return "\n".join(lines) + "\n"


def _render_list(values: list[Any], *, fallback: str) -> str:
    if not values:
        return f"{fallback}\n"
    return "\n".join(f"- {value}" for value in values) + "\n"


def _write_strategy_markdown(path: Path, strategy_record: dict[str, Any], session_config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front_matter = _serialize_front_matter(
        {
            "strategy_id": strategy_record["strategy_id"],
            "strategy_number": strategy_record["strategy_number"],
            "name": strategy_record["name"],
            "league_id": session_config["league_id"],
            "season": session_config["season"],
            "draft_style": session_config["draft_style"],
            "platform": session_config["platform"],
            "draft_type": session_config["draft_type"],
            "reverse_round": bool(session_config.get("reverse_round", False)),
            "created_at": strategy_record["created_at"],
            "agent_rating": strategy_record["agent_rating"],
            "in_effect": strategy_record["in_effect"],
            "retired_at": strategy_record.get("retired_at"),
            "retired_reason": strategy_record.get("retired_reason"),
            "creation_mode": strategy_record["creation_mode"],
            "strategy": strategy_record["strategy"],
            "questionnaire": strategy_record["questionnaire"],
            "validation_feedback": strategy_record["validation_feedback"],
            "collaborating_agents": strategy_record["collaborating_agents"],
        }
    )
    body = [
        front_matter,
        "",
        f"# {strategy_record['name']}",
        "",
        f"Agent rating: {strategy_record['agent_rating']}/100",
        f"In effect: {'yes' if strategy_record['in_effect'] else 'no'}",
        "",
        "## League context",
        _render_list(strategy_record["context_files"], fallback="No league-context files were linked."),
        "## Strategy payload",
        "```json",
        json.dumps(strategy_record["strategy"], indent=2, sort_keys=True, ensure_ascii=False),
        "```",
        "",
        "## Questionnaire transcript",
        _render_questionnaire(strategy_record["questionnaire"]),
        "## Validator feedback",
        _render_list(strategy_record["validation_feedback"], fallback="No validator warnings were recorded."),
        "## Collaboration handoff",
        _render_list(
            [f"{role}: {agent}" for role, agent in strategy_record["collaborating_agents"].items()],
            fallback="No collaborating agents recorded.",
        ),
        "## Mock-draft review prompts",
        _render_list(
            strategy_record["strategy"].get("mock_draft_review") or [],
            fallback="No mock-draft review prompts were recorded yet.",
        ),
    ]
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def _normalize_position_token(value: Any) -> str | None:
    token = str(value or "").strip().upper().replace("DEFENSE", "DST").replace("DEF", "DST")
    if token == "KICKER":
        token = "K"
    return token or None


def _collect_positions(value: Any) -> set[str]:
    if isinstance(value, str):
        token = _normalize_position_token(value)
        return {token} if token else set()
    if isinstance(value, dict):
        positions: set[str] = set()
        for nested in value.values():
            positions.update(_collect_positions(nested))
        return positions
    if isinstance(value, list):
        positions: set[str] = set()
        for nested in value:
            positions.update(_collect_positions(nested))
        return positions
    return set()


def _round_range(value: Any) -> tuple[int | None, int | None]:
    text = str(value or "")
    matches = [int(match) for match in re.findall(r"\d+", text)]
    if not matches:
        return (None, None)
    if "+" in text and len(matches) == 1:
        return (matches[0], None)
    return (matches[0], matches[-1])


def validate_draft_strategy(strategy: dict[str, Any], draft_style: str) -> list[str]:
    if draft_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported draft style: {draft_style}")
    warnings: list[str] = []
    round_plan = strategy.get("round_plan")
    if not isinstance(round_plan, list) or not round_plan:
        warnings.append("Add a round-by-round plan so interviewer, validator, and writer agents can share the same draft path.")
    else:
        for step in round_plan:
            if not isinstance(step, dict):
                continue
            start_round, end_round = _round_range(step.get("rounds"))
            if start_round is None or start_round > 5 or (end_round is not None and end_round < 1):
                continue
            raw_targets = step.get("targets") if isinstance(step.get("targets"), list) else []
            early_window = max(0, 5 - start_round + 1) if end_round is None else max(0, min(end_round, 5) - start_round + 1)
            early_targets = _collect_positions(raw_targets[:early_window] if early_window else raw_targets)
            flagged = sorted(_EARLY_ROUND_RED_FLAGS.intersection(early_targets))
            if flagged:
                warnings.append(
                    f"Early rounds {step.get('rounds')} should not prioritize {', '.join(flagged)}."
                )
    priority_positions = _collect_positions(strategy.get("priority_positions") or strategy.get("priorities"))
    if len(priority_positions) < 2:
        warnings.append("Add at least two priority positions so the strategy can survive early positional runs.")
    early_avoid = _collect_positions(strategy.get("avoid_early"))
    missing_red_flags = sorted(_EARLY_ROUND_RED_FLAGS.difference(early_avoid))
    if missing_red_flags:
        warnings.append(
            "Explicitly fade "
            + ", ".join(missing_red_flags)
            + " in the early rounds so the validator can catch obvious mistakes."
        )
    return warnings


def rate_draft_strategy(
    strategy: dict[str, Any],
    *,
    draft_style: str,
    validation_feedback: Iterable[str] | None = None,
) -> int:
    if draft_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported draft style: {draft_style}")
    feedback = list(validation_feedback or [])
    score = 55
    if strategy.get("summary"):
        score += 8
    if isinstance(strategy.get("round_plan"), list) and strategy["round_plan"]:
        score += 15
    if len(_collect_positions(strategy.get("priority_positions") or strategy.get("priorities"))) >= 2:
        score += 10
    if isinstance(strategy.get("notes"), list) and strategy["notes"]:
        score += 7
    if isinstance(strategy.get("mock_draft_review"), list) and strategy["mock_draft_review"]:
        score += 5
    score -= min(25, len(feedback) * 10)
    return max(25, min(95, score))


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
    questionnaire: list[dict[str, Any]] | None = None,
    validation_feedback: list[str] | None = None,
    agent_rating: int | None = None,
    in_effect: bool = True,
    retired_reason: str | None = None,
    creation_mode: str = "interactive",
    collaborating_agents: dict[str, str] | None = None,
) -> dict[str, Any]:
    if draft_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported draft style: {draft_style}")
    if creation_mode not in {"interactive", "simulation"}:
        raise ValueError("creation_mode must be 'interactive' or 'simulation'")
    style = SUPPORTED_DRAFT_STYLES[draft_style]
    if reverse_round and not style["supports_reverse_round"]:
        raise ValueError(f"Draft style {draft_style} does not support reverse round")
    if validation_feedback is None:
        validation_feedback = validate_draft_strategy(strategy, draft_style)
    if agent_rating is None:
        agent_rating = rate_draft_strategy(strategy, draft_style=draft_style, validation_feedback=validation_feedback)
    questionnaire = deepcopy(questionnaire or [])
    collaborating_agents = deepcopy(collaborating_agents or _DEFAULT_AGENT_ROLES)

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
    created_at = datetime.now(UTC).isoformat()
    strategy_record = {
        "strategy_id": f"strategy-{next_id}",
        "strategy_number": next_id,
        "name": name,
        "created_at": created_at,
        "agent_rating": int(agent_rating),
        "in_effect": bool(in_effect),
        "retired_at": None if in_effect else created_at,
        "retired_reason": retired_reason,
        "creation_mode": creation_mode,
        "questionnaire": questionnaire,
        "validation_feedback": deepcopy(validation_feedback),
        "collaborating_agents": collaborating_agents,
        "context_files": list(style["context_files"]),
        "strategy": deepcopy(strategy),
    }
    strategy_path = _strategy_markdown_path(state_root, draft_style, strategy_record["strategy_id"], name)
    log_path = _strategy_log_path(state_root, draft_style)
    workspace_root = _workspace_root(state_root)
    strategy_record["draft_context_file"] = strategy_path.relative_to(workspace_root).as_posix()
    strategy_record["creation_log_file"] = log_path.relative_to(workspace_root).as_posix()
    strategies.append(strategy_record)
    season_node["session"] = session_config
    season_node["strategies"] = strategies
    league_node[season_key] = season_node
    leagues[league_key] = league_node
    state["leagues"] = leagues
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    _write_strategy_markdown(strategy_path, strategy_record, session_config)
    _append_jsonl(
        log_path,
        {
            "event": "created",
            "created_at": created_at,
            "league_id": session_config["league_id"],
            "season": session_config["season"],
            "draft_style": session_config["draft_style"],
            "platform": session_config["platform"],
            "draft_type": session_config["draft_type"],
            "reverse_round": bool(session_config.get("reverse_round", False)),
            "strategy_id": strategy_record["strategy_id"],
            "strategy_number": strategy_record["strategy_number"],
            "name": strategy_record["name"],
            "agent_rating": strategy_record["agent_rating"],
            "in_effect": strategy_record["in_effect"],
            "creation_mode": strategy_record["creation_mode"],
            "questionnaire": strategy_record["questionnaire"],
            "validation_feedback": strategy_record["validation_feedback"],
            "collaborating_agents": strategy_record["collaborating_agents"],
            "strategy": strategy_record["strategy"],
            "draft_context_file": strategy_record["draft_context_file"],
        },
    )
    return deepcopy(strategy_record)


def load_strategy_creation_log(
    state_root: Path, *, draft_style: str, limit: int | None = None
) -> list[dict[str, Any]]:
    if draft_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported draft style: {draft_style}")
    path = _strategy_log_path(state_root, draft_style)
    if not path.exists():
        return []
    if limit == 0:
        return []
    if limit is None:
        entries: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
    tail: deque[dict[str, Any]] = deque(maxlen=max(0, limit))
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                tail.append(json.loads(line))
    return list(tail)


def _overlay_markdown_strategy(state_root: Path, strategy_record: dict[str, Any]) -> dict[str, Any]:
    draft_context_file = strategy_record.get("draft_context_file")
    if not draft_context_file:
        return strategy_record
    path = _workspace_root(state_root) / str(draft_context_file)
    metadata = _parse_front_matter(path)
    if not metadata:
        return strategy_record
    for key in (
        "name",
        "agent_rating",
        "in_effect",
        "retired_at",
        "retired_reason",
        "creation_mode",
        "strategy",
        "questionnaire",
        "validation_feedback",
        "collaborating_agents",
    ):
        if key in metadata:
            strategy_record[key] = deepcopy(metadata[key])
    return strategy_record


def _refresh_derived_strategy_fields(
    state_root: Path, session_config: dict[str, Any], strategy_record: dict[str, Any]
) -> dict[str, Any]:
    draft_style = str(session_config["draft_style"])
    style = SUPPORTED_DRAFT_STYLES[draft_style]
    strategy_record["context_files"] = list(style["context_files"])
    strategy_record["creation_log_file"] = _strategy_log_path(state_root, draft_style).relative_to(
        _workspace_root(state_root)
    ).as_posix()
    return strategy_record


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
    hydrated = [
        _refresh_derived_strategy_fields(
            state_root,
            session_config,
            _overlay_markdown_strategy(state_root, deepcopy(strategy)),
        )
        for strategy in strategies
    ]
    return {"session": deepcopy(session_config), "strategies": hydrated}


def retire_draft_strategy(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    strategy_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    path = _strategies_path(state_root)
    state = _read_strategy_state(path)
    season_node = state["leagues"].get(str(league_id), {}).get(str(season))
    if not isinstance(season_node, dict):
        raise KeyError(f"No strategies stored for league {league_id} season {season}")
    session_config = season_node.get("session")
    strategies = season_node.get("strategies")
    if not isinstance(session_config, dict) or not isinstance(strategies, list):
        raise ValueError("Draft strategy season entry must include session config and strategy list")
    _validate_session_config(session_config)
    _validate_session_identity(session_config, league_id, season)
    retired_at = datetime.now(UTC).isoformat()
    updated_strategy: dict[str, Any] | None = None
    for index, strategy in enumerate(strategies):
        if not isinstance(strategy, dict):
            raise ValueError("Draft strategy records must be objects")
        if str(strategy.get("strategy_id")) != strategy_id:
            continue
        updated_strategy = deepcopy(strategy)
        updated_strategy["in_effect"] = False
        updated_strategy["retired_at"] = retired_at
        updated_strategy["retired_reason"] = reason
        strategies[index] = updated_strategy
        break
    if updated_strategy is None:
        raise KeyError(f"Unknown strategy_id: {strategy_id}")
    season_node["strategies"] = strategies
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    markdown_strategy = _refresh_derived_strategy_fields(
        state_root,
        session_config,
        _overlay_markdown_strategy(state_root, deepcopy(updated_strategy)),
    )
    markdown_strategy["in_effect"] = False
    markdown_strategy["retired_at"] = retired_at
    markdown_strategy["retired_reason"] = reason
    draft_context_path = _workspace_root(state_root) / str(markdown_strategy["draft_context_file"])
    _write_strategy_markdown(draft_context_path, markdown_strategy, session_config)
    _append_jsonl(
        _strategy_log_path(state_root, str(session_config["draft_style"])),
        {
            "event": "retired",
            "retired_at": retired_at,
            "league_id": session_config["league_id"],
            "season": session_config["season"],
            "draft_style": session_config["draft_style"],
            "strategy_id": updated_strategy["strategy_id"],
            "name": updated_strategy["name"],
            "retired_reason": reason,
        },
    )
    return deepcopy(markdown_strategy)


def simulate_draft_strategy(
    state_root: Path,
    *,
    league_id: str,
    season: int,
    draft_style: str,
    reverse_round: bool = False,
    seed: int | None = None,
) -> dict[str, Any]:
    if draft_style not in SUPPORTED_DRAFT_STYLES:
        raise ValueError(f"Unsupported draft style: {draft_style}")
    choices = _SIMULATED_STRATEGIES[draft_style]
    if draft_style == "espn_snake":
        choices = [
            choice for choice in choices if bool(choice.get("reverse_round", False)) == bool(reverse_round)
        ]
        if not choices:
            raise ValueError(f"No simulated {draft_style} presets match reverse_round={reverse_round}")
    selection = deepcopy(random.Random(seed).choice(choices))
    return save_draft_strategy(
        state_root,
        league_id=league_id,
        season=season,
        draft_style=draft_style,
        reverse_round=reverse_round,
        name=selection["name"],
        strategy=selection["strategy"],
        questionnaire=selection.get("questionnaire"),
        creation_mode="simulation",
    )


def latest_trending_snapshot(state_root: Path, provider: str = "sleeper") -> Path:
    snapshots = sorted(
        (state_root / "players" / "trending" / "raw").glob(f"{provider}-trending-*.json"),
        reverse=True,
    )
    if not snapshots:
        raise FileNotFoundError(
            f"No {provider} trending snapshot found under "
            f"{state_root / 'players' / 'trending' / 'raw'}"
        )
    return snapshots[0]


def load_trending(snapshot: Path) -> dict[str, Any]:
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("add"), list) or not isinstance(
        payload.get("drop"), list
    ):
        raise ValueError("Trending snapshot must include 'add' and 'drop' lists")
    return payload


def query_trending_players(
    trending: dict[str, Any],
    players: Iterable[dict[str, Any]] | None = None,
    *,
    direction: str = "add",
    position: str | None = None,
    team: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    if direction not in ("add", "drop"):
        raise ValueError("direction must be 'add' or 'drop'")
    entries = trending.get(direction) or []
    player_index: dict[str, dict[str, Any]] = {}
    for player in players or []:
        provider_id = player.get("provider_id")
        if provider_id is not None:
            player_index[str(provider_id)] = player
    position_filter = position.upper() if position else None
    team_filter = team.upper() if team else None
    results = []
    for entry in entries:
        if not isinstance(entry, dict) or "player_id" not in entry:
            raise ValueError("Trending entries must be objects with a 'player_id' field")
        provider_id = str(entry["player_id"])
        player = player_index.get(provider_id, {})
        fantasy_positions = {str(value).upper() for value in player.get("fantasy_positions") or []}
        if position_filter and position_filter not in fantasy_positions:
            continue
        team_value = str(player.get("team") or "").upper()
        if team_filter and team_value != team_filter:
            continue
        results.append(
            {
                "provider_id": provider_id,
                "count": entry.get("count"),
                "full_name": player.get("full_name"),
                "position": player.get("position"),
                "fantasy_positions": sorted(fantasy_positions),
                "team": player.get("team"),
                "status": player.get("status"),
            }
        )
    return results[: max(0, limit)]


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
