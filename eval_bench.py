import os
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players
import glob

workspace = Path(".")
config = load_config(workspace)
league_id = config.get("dynasty_league_id")
user_id = config.get("sleeper_user_id")

provider = get_provider("sleeper", config)
week = 5
matchup_data = provider.get_user_matchup(league_id, user_id, week)
user_matchup = matchup_data["user"]
user_starters = [pid for pid in user_matchup.get("starters", []) if pid != "0"]
user_players = user_matchup.get("players", [])
user_bench = [pid for pid in user_players if pid not in user_starters]

snapshot_paths = glob.glob(str(workspace / "state" / "players" / "raw" / "sleeper-players-*.json"))
latest_snapshot = max(snapshot_paths)
all_players_list = load_players(Path(latest_snapshot))
all_players = {str(p.get("player_id")): p for p in all_players_list}

print("=== BENCH PLAYERS ===")
for pid in user_bench:
    p = all_players.get(pid, {})
    name = p.get("full_name") or p.get("first_name") or f"Player {pid}"
    pos = p.get("position")
    team = p.get("team")
    age = p.get("age")
    years_exp = p.get("years_exp")
    status = p.get("status")
    injury = p.get("injury_status")
    print(f"{name} ({pos} - {team}) - Age: {age}, Exp: {years_exp}, Status: {status}, Injury: {injury}")
