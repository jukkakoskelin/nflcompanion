"""Antigravity PreInvocation hook to inject Sleeper trending player context."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure src is in python path
repo_root = Path(__file__).resolve().parent.parent.parent
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from nflcompanion.mcp_server import fetch_trending, save_trending_snapshot
from nflcompanion.state_store import (
    latest_snapshot,
    latest_trending_snapshot,
    load_players,
    load_trending,
    query_trending_players,
)

TOP_N = 10
MAX_AGE_MINUTES = 15


def get_trending_summary(state_root: Path) -> str | None:
    # Check existing snapshot
    needs_fetch = False
    try:
        current_path = latest_trending_snapshot(state_root)
        stat = current_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        age_minutes = (datetime.now(timezone.utc) - mtime).total_seconds() / 60.0
        if age_minutes >= MAX_AGE_MINUTES:
            needs_fetch = True
    except FileNotFoundError:
        needs_fetch = True

    if needs_fetch:
        try:
            retrieved_at = datetime.now(timezone.utc)
            add_entries = fetch_trending("add", lookback_hours=24, limit=25, timeout=10)
            drop_entries = fetch_trending("drop", lookback_hours=24, limit=25, timeout=10)
            save_trending_snapshot(
                add_entries=add_entries,
                drop_entries=drop_entries,
                state_root=state_root,
                retrieved_at=retrieved_at,
                lookback_hours=24,
                limit=25,
            )
        except Exception:
            # Fall back to existing cached snapshot if fetch fails
            pass

    try:
        snapshot_path = latest_trending_snapshot(state_root)
        trending = load_trending(snapshot_path)
    except FileNotFoundError:
        return None

    try:
        player_snapshot = latest_snapshot(state_root)
        players = load_players(player_snapshot)
    except FileNotFoundError:
        players = []

    top_adds = query_trending_players(trending, players=players, direction="add", limit=TOP_N)
    top_drops = query_trending_players(trending, players=players, direction="drop", limit=TOP_N)

    def format_entry(p: dict) -> str:
        name = p.get("full_name") or f"player_id {p.get('provider_id')}"
        pos = "/".join(p.get("fantasy_positions") or []) or p.get("position") or "?"
        team = f", {p['team']}" if p.get("team") else ""
        count = p.get("count", 0)
        return f"{name} ({pos}{team}) - {count}"

    adds_str = "; ".join(format_entry(p) for p in top_adds) or "none"
    drops_str = "; ".join(format_entry(p) for p in top_drops) or "none"

    return (
        f"Sleeper trending players (last 24h):\n"
        f"Top adds: {adds_str}\n"
        f"Top drops: {drops_str}\n"
        f"Use sleeper_query_trending_players for filtered lists."
    )


def main() -> int:
    # Read payload from stdin
    try:
        stdin_content = sys.stdin.read()
        payload = json.loads(stdin_content) if stdin_content.strip() else {}
    except Exception:
        payload = {}

    state_root = repo_root / "state"
    summary = get_trending_summary(state_root)

    output: dict[str, Any] = {"injectSteps": []}
    if summary:
        output["injectSteps"].append({"ephemeralMessage": summary})

    sys.stdout.write(json.dumps(output) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
