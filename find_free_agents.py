import os
import json
import glob
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players

workspace = Path(".")
config = load_config(workspace)
league_id = config.get("dynasty_league_id")

provider = get_provider("sleeper", config)
rosters = provider.get_league_rosters(league_id)

rostered_ids = set()
for r in rosters:
    for pid in r.get("players", []):
        rostered_ids.add(str(pid))

# Load trending players
trending_paths = glob.glob(str(workspace / "state" / "players" / "trending" / "raw" / "sleeper-trending-*.json"))
latest_trending = max(trending_paths)
with open(latest_trending, "r", encoding="utf-8") as f:
    trending_data = json.load(f)

# Load all players
snapshot_paths = glob.glob(str(workspace / "state" / "players" / "raw" / "sleeper-players-*.json"))
latest_snapshot = max(snapshot_paths)
all_players_list = load_players(Path(latest_snapshot))
all_players = {str(p.get("player_id")): p for p in all_players_list}

print("=== TOP TRENDING AVAILABLE FREE AGENTS ===")
adds = trending_data.get("add", [])
found = 0
for entry in adds:
    pid = str(entry.get("player_id"))
    if pid not in rostered_ids and pid != "0":
        p = all_players.get(pid, {})
        name = p.get("full_name") or p.get("first_name") or f"Player {pid}"
        pos = p.get("position")
        team = p.get("team")
        age = p.get("age")
        years_exp = p.get("years_exp")
        print(f"{name} ({pos} - {team}) - Age: {age}, Exp: {years_exp} - Trending Adds: {entry.get('count')}")
        found += 1
        if found >= 15:
            break

if found == 0:
    print("No trending players are available.")
