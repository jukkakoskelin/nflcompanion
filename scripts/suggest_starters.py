import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players
from nflcompanion.draft_companion import NFL_BYE_WEEKS_2026

import sys
sys.path.insert(0, str(Path(__file__).parent))
import fetch_sleeper_players

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--week", type=int, help="Override the NFL week")
    parser.add_argument("--platform", type=str, default="sleeper", choices=["sleeper", "espn"], help="Platform to generate suggestions for")
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

    provider = get_provider(platform, config)
    
    # 1. Determine week
    week = args.week
    if not week:
        try:
            state = provider.get_nfl_state()
            if state.get("season_type") != "regular":
                print("Not in regular season. Use --week to override.")
                return 0
            week = state.get("leg")
        except Exception as e:
            print(f"Failed to fetch NFL state: {e}")
            return 1
    
    if not week:
        print("Could not determine NFL week.")
        return 1
        
    print(f"Generating matchup suggestions for Week {week}...")
    
    # 2. Get matchup
    matchup_data = provider.get_user_matchup(league_id, user_id, week)
    user_matchup = matchup_data["user"]
    opponent_matchup = matchup_data["opponent"]
    
    if not opponent_matchup:
        print(f"No opponent found for week {week}. (Bye week?)")
        return 0

    # 3. Load player state
    print("Fetching latest Sleeper player data...")
    raw_payload = fetch_sleeper_players.fetch_players()
    retrieved_at = datetime.now(timezone.utc)
    snapshot_path = fetch_sleeper_players.save_snapshot(raw_payload, workspace / "state", retrieved_at)
    all_players_list = load_players(snapshot_path)
    all_players = {str(p.get("player_id")): p for p in all_players_list}
    
    fallback_metadata = provider.get_player_fallback_metadata() if hasattr(provider, 'get_player_fallback_metadata') else {}
    
    if platform == "espn":
        espn_to_sleeper = {str(p.get("espn_id")): str(p.get("player_id")) for p in all_players_list if p.get("espn_id")}
        def map_ids(id_list):
            mapped = []
            for pid in id_list:
                str_pid = str(pid)
                if str_pid in espn_to_sleeper:
                    mapped.append(espn_to_sleeper[str_pid])
                else:
                    mapped.append(str_pid)
                    if str_pid in fallback_metadata and str_pid not in all_players:
                        all_players[str_pid] = fallback_metadata[str_pid]
            return mapped
            
        user_matchup["starters"] = map_ids(user_matchup.get("starters", []))
        user_matchup["players"] = map_ids(user_matchup.get("players", []))
        opponent_matchup["starters"] = map_ids(opponent_matchup.get("starters", []))
        if opponent_matchup.get("players"):
            opponent_matchup["players"] = map_ids(opponent_matchup.get("players", []))
    
    # Extract players
    user_starters = [pid for pid in user_matchup.get("starters", []) if pid != "0"]
    user_players = user_matchup.get("players", [])
    user_bench = [pid for pid in user_players if pid not in user_starters]
    
    opponent_starters = [pid for pid in opponent_matchup.get("starters", []) if pid != "0"]
    
    # 4. Analyze user starters
    issues = []
    for pid in user_starters:
        p = all_players.get(pid, {})
        name = p.get("full_name") or p.get("first_name") or f"Player {pid}"
        team = p.get("team")
        status = p.get("status")
        injury = p.get("injury_status")
        
        flags = []
        if injury and injury.lower() in ("out", "doubtful", "questionable", "ir"):
            flags.append(f"Injury: {injury}")
        if status and status.lower() in ("suspended", "inactive"):
            flags.append(f"Status: {status}")
        if team and NFL_BYE_WEEKS_2026.get(team) == week:
            flags.append("BYE WEEK")
            
        if flags:
            issues.append(f"- **{name}** ({p.get('position')} - {team}): {', '.join(flags)}")
            
    # 5. Output report
    report_lines = [
        f"# Week {week} Dynasty Matchup Suggestion",
        "",
        "## Your Starter Issues",
        ""
    ]
    if issues:
        report_lines.extend(issues)
        report_lines.append("")
        report_lines.append("### Bench Alternatives")
        for pid in user_bench:
            p = all_players.get(pid, {})
            name = p.get("full_name") or p.get("first_name") or f"Player {pid}"
            team = p.get("team")
            if team and NFL_BYE_WEEKS_2026.get(team) != week and str(p.get("injury_status") or "").lower() not in ("out", "ir", "doubtful"):
                report_lines.append(f"- **{name}** ({p.get('position')} - {team}) - Healthy")
    else:
        report_lines.append("No immediate red flags (byes/injuries) found among your starters.")
        
    report_lines.extend([
        "",
        "## Opponent's Starters",
        ""
    ])
    
    for pid in opponent_starters:
        p = all_players.get(pid, {})
        name = p.get("full_name") or p.get("first_name") or f"Player {pid}"
        team = p.get("team")
        injury = p.get("injury_status")
        flag = f" (Injury: {injury})" if injury and injury.lower() in ("out", "questionable", "doubtful") else ""
        report_lines.append(f"- **{name}** ({p.get('position')} - {team}){flag}")

    report_path = workspace / "weekly_matchup_suggestion.md"
    report_text = "\n".join(report_lines)
    report_path.write_text(report_text, encoding="utf-8")
    
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report_text + "\n")
            
    print(f"Report written to {report_path.name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
