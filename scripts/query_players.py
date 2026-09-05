"""Temporary canvas-facing query interface for player state snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nflcompanion.state_store import latest_snapshot, load_players, query_players


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--name")
    parser.add_argument("--position")
    parser.add_argument("--team")
    parser.add_argument("--active-only", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be non-negative")
    snapshot = latest_snapshot(args.state_root)
    results = query_players(
        load_players(snapshot), name=args.name, position=args.position,
        team=args.team, active_only=args.active_only, limit=args.limit
    )
    print(json.dumps({"snapshot": str(snapshot), "count": len(results), "players": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
