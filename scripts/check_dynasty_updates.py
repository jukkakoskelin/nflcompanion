import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players

# Import fetcher
import sys
sys.path.insert(0, str(Path(__file__).parent))
import fetch_sleeper_players

def fetch_player_news(player_id: str) -> str:
    import urllib.request
    query = """
    query {
      get_player_news(sport: "nfl", player_id: "%s") {
        metadata
      }
    }
    """ % player_id
    req = urllib.request.Request(
        'https://sleeper.app/graphql',
        data=json.dumps({'query': query}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.load(response)
            news_items = data.get("data", {}).get("get_player_news", [])
            if news_items:
                metadata = news_items[0].get("metadata", {})
                title = metadata.get("title", "")
                desc = metadata.get("description", "")
                if title and desc:
                    return f"{title}: {desc}"
                elif desc:
                    return desc
                elif title:
                    return title
    except Exception as e:
        print(f"Failed to fetch news for {player_id}: {e}")
    return "New update available"

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--platform", type=str, default="sleeper", choices=["sleeper", "espn"], help="Platform to check updates for")
    args = parser.parse_args()
    
    workspace = args.workspace
    platform = args.platform
    config = load_config(workspace)
    
    if platform == "espn":
        from nflcompanion.config import ensure_espn_config
        config = ensure_espn_config(workspace)
        league_id = config.get("espn_league_id")
        user_id = config.get("espn_team_id")
    else:
        league_id = config.get("dynasty_league_id")
        user_id = config.get("sleeper_user_id")
    
    if not league_id or not user_id:
        print(f"Missing config for {platform}.")
        return 1

    print(f"Fetching roster for user {user_id} in league {league_id}...")
    provider = get_provider(platform, config)
    roster_player_ids = provider.get_user_roster(league_id, user_id)
    if not roster_player_ids:
        print("No players found on roster.")
        return 1

    print("Fetching latest Sleeper player data...")
    raw_payload = fetch_sleeper_players.fetch_players()
    # Save the snapshot locally so we can load it through state_store
    retrieved_at = datetime.now(timezone.utc)
    snapshot_path = fetch_sleeper_players.save_snapshot(raw_payload, workspace / "state", retrieved_at)
    
    all_players_list = load_players(snapshot_path)
    all_players = {str(p.get("player_id")): p for p in all_players_list}
    
    fallback_metadata = provider.get_player_fallback_metadata() if hasattr(provider, 'get_player_fallback_metadata') else {}
    
    if platform == "espn":
        espn_to_sleeper = {str(p.get("espn_id")): str(p.get("player_id")) for p in all_players_list if p.get("espn_id")}
        
        mapped_roster = []
        for pid in roster_player_ids:
            str_pid = str(pid)
            if str_pid in espn_to_sleeper:
                mapped_roster.append(espn_to_sleeper[str_pid])
            else:
                mapped_roster.append(str_pid)
                if str_pid in fallback_metadata and str_pid not in all_players:
                    all_players[str_pid] = fallback_metadata[str_pid]
        roster_player_ids = mapped_roster
    
    # State file for PR tracking
    roster_state_path = workspace / "state" / "rosters" / f"{platform}_dynasty_{league_id}_state.json"
    roster_state_path.parent.mkdir(parents=True, exist_ok=True)
    
    previous_state = {}
    if roster_state_path.exists():
        previous_state = json.loads(roster_state_path.read_text(encoding="utf-8"))
        
    current_state = {}
    changes = []
    
    attributes_to_track = ["status", "injury_status", "depth_chart_order", "news_updated", "team"]
    
    for pid in roster_player_ids:
        player_data = all_players.get(pid)
        if not player_data:
            continue
            
        p_name = player_data.get("full_name") or f"Player {pid}"
        p_state = {attr: player_data.get(attr) for attr in attributes_to_track}
        current_state[pid] = {"name": p_name, **p_state}
        
        prev_p = previous_state.get(pid)
        if prev_p:
            for attr in attributes_to_track:
                old_val = prev_p.get(attr)
                new_val = p_state.get(attr)
                if old_val != new_val:
                    if attr == "news_updated":
                        news = fetch_player_news(pid)
                        changes.append(f"- **{p_name}**: News Updated - {news}")
                    else:
                        changes.append(f"- **{p_name}**: `{attr}` changed from `{old_val}` to `{new_val}`")
        else:
            changes.append(f"- **{p_name}**: Added to roster tracking.")

    # Write new state
    roster_state_path.write_text(json.dumps(current_state, indent=2, sort_keys=True), encoding="utf-8")
    
    # Write report
    report_path = workspace / "dynasty_update_report.md"
    report_lines = [f"# Dynasty Roster Update ({retrieved_at.strftime('%Y-%m-%d')})", ""]
    if changes:
        report_lines.append("## Changes Detected")
        report_lines.extend(changes)
    else:
        report_lines.append("No changes detected in tracked attributes.")
        
    report_text = "\n".join(report_lines)
    report_path.write_text(report_text, encoding="utf-8")
    
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report_text + "\n")
    
    if changes:
        print("Changes detected.")
        # We can create a github action output
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("has_changes=true\n")
    else:
        print("No changes.")
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("has_changes=false\n")
                
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
