"""Temporary canvas-facing query interface for trending player state snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nflcompanion.state_store import (
    latest_snapshot,
    latest_trending_snapshot,
    load_players,
    load_trending,
    query_trending_players,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--direction", choices=("add", "drop"), default="add")
    parser.add_argument("--position")
    parser.add_argument("--team")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    trending_snapshot = latest_trending_snapshot(args.state_root)
    trending = load_trending(trending_snapshot)
    try:
        players = load_players(latest_snapshot(args.state_root))
    except FileNotFoundError:
        players = []
    results = query_trending_players(
        trending, players, direction=args.direction, position=args.position,
        team=args.team, limit=args.limit
    )
    print(
        json.dumps(
            {
                "snapshot": str(trending_snapshot),
                "direction": args.direction,
                "count": len(results),
                "players": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
