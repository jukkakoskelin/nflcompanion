import argparse
import sys
from pathlib import Path

# Ensure src is in python path so we can import nflcompanion
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nflcompanion.espn_sync import sync_espn_data

def main():
    parser = argparse.ArgumentParser(description="Sync ESPN Roster, Matchup, and Free Agents")
    parser.add_argument("--limit", type=int, default=100, help="Number of free agents to fetch")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parent.parent
    try:
        sync_data = sync_espn_data(workspace_root, args.limit)
        
        roster = sync_data.get("roster", [])
        matchup = sync_data.get("matchup")
        free_agents = sync_data.get("free_agents", [])
        
        out_path = workspace_root / "state" / "espn" / "espn_sync_state.json"
        print(f"Successfully synced ESPN data to {out_path}")
        print(f"Roster size: {len(roster)}")
        if matchup:
            user_pts = matchup.get("user", {}).get("points", 0)
            opp_pts = matchup.get("opponent", {}).get("points", 0)
            print(f"Matchup: User {user_pts} vs Opponent {opp_pts}")
        print(f"Free Agents fetched: {len(free_agents)}")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
