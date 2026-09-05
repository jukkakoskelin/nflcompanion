"""Fetch and persist a dated Sleeper trending add/drop snapshot."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

URL_TEMPLATE = "https://api.sleeper.app/v1/players/nfl/trending/{direction}"
DIRECTIONS = ("add", "drop")


def atomic_write(path: Path, content: str) -> None:
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


def fetch_trending(
    direction: str, *, lookback_hours: int = 24, limit: int = 25, timeout: int = 30
) -> list[dict[str, Any]]:
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}")
    url = f"{URL_TEMPLATE.format(direction=direction)}?lookback_hours={lookback_hours}&limit={limit}"
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
    lookback_hours: int,
    limit: int,
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
    atomic_write(raw_path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
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
    atomic_write(manifest_path, manifest)
    return raw_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    retrieved_at = datetime.now(timezone.utc)
    add_entries = fetch_trending(
        "add", lookback_hours=args.lookback_hours, limit=args.limit, timeout=args.timeout
    )
    drop_entries = fetch_trending(
        "drop", lookback_hours=args.lookback_hours, limit=args.limit, timeout=args.timeout
    )
    path = save_trending_snapshot(
        add_entries=add_entries,
        drop_entries=drop_entries,
        state_root=args.state_root,
        retrieved_at=retrieved_at,
        lookback_hours=args.lookback_hours,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "snapshot": str(path),
                "add_count": len(add_entries),
                "drop_count": len(drop_entries),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
