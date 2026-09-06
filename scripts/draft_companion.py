"""Run the local NFL draft companion workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from nflcompanion.draft_companion import (
    batch_record_observed_picks,
    create_draft_session,
    load_draft_session,
    next_pick_preview,
    record_observed_pick,
    record_pick,
    recommend_candidates,
)
from nflcompanion.sleeper_sync import sync_sleeper_draft_picks
from nflcompanion.state_store import (
    latest_snapshot,
    latest_trending_snapshot,
    load_players,
    load_trending,
)


def _json_object(value: str, argument_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"{argument_name} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise argparse.ArgumentTypeError(f"{argument_name} must be a JSON object")
    return payload


def _session_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--league-id", required=True)
    parser.add_argument("--season", type=int, required=True)


def _load_local_context(state_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    players = load_players(latest_snapshot(state_root))
    try:
        trending = load_trending(latest_trending_snapshot(state_root))
    except FileNotFoundError:
        trending = None
    return players, trending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="create a draft session")
    _session_arguments(init_parser)
    init_parser.add_argument("--draft-style", required=True)
    init_parser.add_argument("--team-count", type=int, required=True)
    init_parser.add_argument("--user-slot", type=int, required=True)
    init_parser.add_argument("--active-strategy-id")
    init_parser.add_argument("--strategy-json", type=lambda value: _json_object(value, "--strategy-json"), default={})
    init_parser.add_argument("--reverse-round", action="store_true")
    init_parser.add_argument("--decision-window-seconds", type=int, default=90)

    recommend_parser = commands.add_parser("recommend", help="rank 2-4 local player candidates")
    _session_arguments(recommend_parser)
    recommend_parser.add_argument("candidates", nargs="+")

    record_parser = commands.add_parser("record-pick", help="record a confirmed user pick")
    _session_arguments(record_parser)
    record_parser.add_argument("--provider-id", required=True)
    record_parser.add_argument("--full-name", required=True)
    record_parser.add_argument("--position")
    record_parser.add_argument("--team")
    record_parser.add_argument("--overall-pick", type=int)
    record_parser.add_argument("--idempotency-key")
    record_parser.add_argument(
        "--confirmed", action="store_true", help="required explicit confirmation gate"
    )

    observe_parser = commands.add_parser("observe-pick", help="record an opponent pick")
    _session_arguments(observe_parser)
    observe_parser.add_argument("--provider-id", required=True)
    observe_parser.add_argument("--full-name", required=True)
    observe_parser.add_argument("--position")
    observe_parser.add_argument("--team")
    observe_parser.add_argument("--overall-pick", type=int, required=True)

    batch_observe_parser = commands.add_parser("observe-batch", help="record multiple opponent picks in a batch")
    _session_arguments(batch_observe_parser)
    batch_observe_parser.add_argument(
        "--picks-json",
        type=lambda v: json.loads(v),
        required=True,
        help="JSON array of objects with provider_id, overall_pick, and optional full_name/position/team",
    )

    sync_sleeper_parser = commands.add_parser("sync-sleeper", help="poll and sync live picks from a Sleeper draft room")
    _session_arguments(sync_sleeper_parser)
    sync_sleeper_parser.add_argument("--draft-id", required=True, help="Sleeper draft ID")

    preview_parser = commands.add_parser("next-pick", help="show the next user pick")
    _session_arguments(preview_parser)

    args = parser.parse_args()
    if args.command == "init":
        result = create_draft_session(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            draft_style=args.draft_style,
            team_count=args.team_count,
            user_slot=args.user_slot,
            active_strategy=args.strategy_json,
            active_strategy_id=args.active_strategy_id,
            reverse_round=args.reverse_round,
            decision_window_seconds=args.decision_window_seconds,
        )
    elif args.command == "recommend":
        if not 2 <= len(args.candidates) <= 4:
            parser.error("recommend requires between 2 and 4 candidate inputs")
        loaded = load_draft_session(args.state_root, league_id=args.league_id, season=args.season)
        players, trending = _load_local_context(args.state_root)
        drafted_ids = [item["provider_id"] for item in loaded["session"].get("selected_players", [])]
        result = recommend_candidates(
            players,
            args.candidates,
            strategy=loaded["living_strategy"],
            drafted_provider_ids=drafted_ids,
            trending=trending,
        )
        recommendation_dir = args.state_root / "drafts" / args.league_id / str(args.season) / "recommendations"
        recommendation_dir.mkdir(parents=True, exist_ok=True)
        recommendation_path = recommendation_dir / f"{result['generated_at'].replace(':', '-')}.json"
        recommendation_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        result["recommendation_file"] = str(recommendation_path)
    elif args.command == "record-pick":
        result = record_pick(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            provider_id=args.provider_id,
            player={
                "provider_id": args.provider_id,
                "full_name": args.full_name,
                "position": args.position,
                "team": args.team,
            },
            confirmed=args.confirmed,
            idempotency_key=args.idempotency_key,
            overall_pick=args.overall_pick,
        )
    elif args.command == "observe-pick":
        result = record_observed_pick(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            provider_id=args.provider_id,
            player={
                "full_name": args.full_name,
                "position": args.position,
                "team": args.team,
            },
            overall_pick=args.overall_pick,
        )
    elif args.command == "observe-batch":
        players, _ = _load_local_context(args.state_root)
        result = batch_record_observed_picks(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            picks=args.picks_json,
            all_players=players,
        )
    elif args.command == "sync-sleeper":
        players, _ = _load_local_context(args.state_root)
        result = sync_sleeper_draft_picks(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            draft_id=args.draft_id,
            players=players,
        )
    else:
        players, trending = _load_local_context(args.state_root)
        result = next_pick_preview(
            args.state_root,
            league_id=args.league_id,
            season=args.season,
            players=players,
            trending=trending,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
