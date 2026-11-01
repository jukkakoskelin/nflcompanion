import os
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players
from nflcompanion.draft_companion import NFL_BYE_WEEKS_2026

workspace = Path(".")
config = load_config(workspace)
league_id = config.get("dynasty_league_id")
user_id = config.get("sleeper_user_id")

provider = get_provider("sleeper", config)
try:
    nfl_state = provider.get_nfl_state()
    week = nfl_state.get("leg", 6)
except Exception:
    week = 6
matchup_data = provider.get_user_matchup(league_id, user_id, week)
user_matchup = matchup_data["user"]
user_starters = [pid for pid in user_matchup.get("starters", []) if pid != "0"]

import glob
snapshot_paths = glob.glob(str(workspace / "state" / "players" / "raw" / "sleeper-players-*.json"))
latest_snapshot = max(snapshot_paths)

all_players_list = load_players(Path(latest_snapshot))
all_players = {str(p.get("player_id")): p for p in all_players_list}

print(f"=== WEEK {week} STARTERS ===")
for pid in user_starters:
    p = all_players.get(pid, {})
    name = p.get("full_name") or p.get("first_name") or f"Player {pid}"
    team = p.get("team")
    pos = p.get("position")
    bye = NFL_BYE_WEEKS_2026.get(team)
    print(f"{name} ({pos} - {team}) - BYE: {bye}")
