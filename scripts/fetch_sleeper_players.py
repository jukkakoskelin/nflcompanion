"""Fetch and persist a dated Sleeper player snapshot."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

URL = "https://api.sleeper.app/v1/players/nfl"


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


def fetch_players(url: str = URL, timeout: int = 30) -> dict[str, Any]:
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
    atomic_write(raw_path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    manifest = (
        f"---\nprovider: sleeper\nretrieved_at: {retrieved_at.isoformat()}\n"
        f"endpoint: {URL}\nrecord_count: {len(payload)}\nraw_snapshot: "
        f"{raw_path.relative_to(state_root).as_posix()}\n---\n\n"
        "# Sleeper player snapshot\n\n"
        "This is an immutable, read-only provider snapshot. Use the raw JSON "
        "for complete fields and the canonical state reader for queries.\n"
    )
    atomic_write(manifest_path, manifest)
    return raw_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=Path("state"))
    parser.add_argument("--url", default=URL, help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    retrieved_at = datetime.now(timezone.utc)
    payload = fetch_players(args.url, args.timeout)
    path = save_snapshot(payload, args.state_root, retrieved_at)
    print(json.dumps({"snapshot": str(path), "record_count": len(payload)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
