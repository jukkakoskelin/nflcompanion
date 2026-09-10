from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path("scripts").absolute()))
import fetch_sleeper_players

def main():
    workspace = Path(".")
    config = load_config(workspace)
    league_id = config.get("dynasty_league_id")
    user_id = config.get("sleeper_user_id")
    provider = get_provider("sleeper")
    
    try:
        week = provider.get_nfl_state().get("leg")
    except Exception:
        week = 1
        
    matchup_data = provider.get_user_matchup(league_id, user_id, week)
    user_starters = [pid for pid in matchup_data["user"].get("starters", []) if pid != "0"]
    
    raw = fetch_sleeper_players.fetch_players()
    snapshot_path = fetch_sleeper_players.save_snapshot(raw, workspace / "state", datetime.now(timezone.utc))
    all_players = {str(p.get("player_id")): p for p in load_players(snapshot_path)}
    
    print("STARTERS:")
    for pid in user_starters:
        p = all_players.get(pid, {})
        print(f"{p.get('full_name')} ({p.get('position')} - {p.get('team')})")

if __name__ == "__main__":
    main()
