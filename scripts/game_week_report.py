import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from nflcompanion.config import load_config
from nflcompanion.providers import get_provider
from nflcompanion.state_store import load_players, latest_trending_snapshot, load_trending
from nflcompanion.draft_companion import NFL_BYE_WEEKS_2026

sys.path.insert(0, str(Path(__file__).parent))
import fetch_sleeper_players
import fetch_sleeper_trending

def _get_player_name(all_players, pid):
    p = all_players.get(str(pid), {})
    return p.get("full_name") or p.get("first_name") or f"Player {pid}"

def _get_player_pos_team(all_players, pid):
    p = all_players.get(str(pid), {})
    return p.get("position", "UNK"), p.get("team", "FA")

def analyze_previous_week(provider, platform, league_id, user_id, prev_week, all_players, espn_to_sleeper):
    if prev_week < 1:
        return ["No previous week to analyze."]
        
    try:
        matchup_data = provider.get_user_matchup(league_id, user_id, prev_week)
    except Exception as e:
        return [f"Could not load data for previous week {prev_week}: {e}"]
        
    user_matchup = matchup_data.get("user")
    if not user_matchup:
        return ["No user matchup data for previous week."]
        
    report = [f"## Week {prev_week} Performance Summary", ""]
    
    # Calculate points and projections
    team_pts = 0.0
    team_proj = 0.0
    
    player_pts_map = {}
    player_proj_map = {}
    
    if platform == "espn":
        team_pts = user_matchup.get("points", 0.0)
        team_proj = user_matchup.get("projected_points", 0.0)
        player_pts_map = user_matchup.get("player_points", {})
        player_proj_map = user_matchup.get("player_projected", {})
        
        def map_ids(id_list):
            return [espn_to_sleeper.get(str(pid), str(pid)) for pid in id_list]
            
        starters = map_ids(user_matchup.get("starters", []))
        players = map_ids(user_matchup.get("players", []))
        
        # Remap maps to sleeper IDs
        new_pts_map = {}
        new_proj_map = {}
        for k, v in player_pts_map.items():
            new_pts_map[espn_to_sleeper.get(str(k), str(k))] = v
        for k, v in player_proj_map.items():
            new_proj_map[espn_to_sleeper.get(str(k), str(k))] = v
        player_pts_map = new_pts_map
        player_proj_map = new_proj_map
        
    else:
        # Sleeper
        team_pts = user_matchup.get("points", 0.0)
        starters = [str(pid) for pid in user_matchup.get("starters", []) if str(pid) != "0"]
        players = [str(pid) for pid in user_matchup.get("players", [])]
        
        # In Sleeper, starters_points corresponds directly to starters array
        s_pts = user_matchup.get("starters_points", [])
        for i, pid in enumerate(user_matchup.get("starters", [])):
            if str(pid) != "0" and i < len(s_pts):
                player_pts_map[str(pid)] = s_pts[i]
                
        # To get bench points, we might not have them easily without a detailed stats pull,
        # but let's try our best. Actually Sleeper matchup provides 'players_points' dictionary.
        player_pts_map.update(user_matchup.get("players_points", {}))
        
        # Projections
        proj_map = provider.get_projections(prev_week)
        for pid in players:
            player_proj_map[pid] = proj_map.get(pid, 0.0)
            if pid in starters:
                team_proj += player_proj_map[pid]

    diff = team_pts - team_proj
    diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"
    
    report.append(f"- **Total Points:** {team_pts:.2f} (Projected: {team_proj:.2f} | Diff: {diff_str})")
    
    # Best and worst starters
    starter_pts = [(pid, player_pts_map.get(pid, 0.0), player_proj_map.get(pid, 0.0)) for pid in starters]
    starter_pts.sort(key=lambda x: x[1], reverse=True)
    
    if starter_pts:
        top_pid, top_pts, top_proj = starter_pts[0]
        worst_pid, worst_pts, worst_proj = starter_pts[-1]
        
        top_name = _get_player_name(all_players, top_pid)
        worst_name = _get_player_name(all_players, worst_pid)
        
        report.append(f"- **Top Scorer:** {top_name} with {top_pts:.2f} pts (Proj: {top_proj:.2f})")
        report.append(f"- **Worst Scorer:** {worst_name} with {worst_pts:.2f} pts (Proj: {worst_proj:.2f})")

    # Bench hindsight
    bench = [p for p in players if p not in starters]
    hindsight = []
    
    for b_pid in bench:
        b_pts = player_pts_map.get(b_pid, 0.0)
        b_pos, _ = _get_player_pos_team(all_players, b_pid)
        
        # Did this bench player outscore a starter of the SAME position?
        outscored_starters = []
        for s_pid, s_pts, s_proj in starter_pts:
            s_pos, _ = _get_player_pos_team(all_players, s_pid)
            if s_pos == b_pos and b_pts > s_pts:
                outscored_starters.append((s_pid, s_pts))
                
        if outscored_starters:
            # Sort by worst starter outscored
            outscored_starters.sort(key=lambda x: x[1])
            s_pid, s_pts = outscored_starters[0]
            b_name = _get_player_name(all_players, b_pid)
            s_name = _get_player_name(all_players, s_pid)
            hindsight.append(f"- **Bench Hindsight:** {b_name} ({b_pts:.2f} pts) outscored {s_name} ({s_pts:.2f} pts).")
            
    if hindsight:
        report.append("")
        report.extend(hindsight)
        
    return report

def analyze_next_week(provider, platform, league_id, user_id, week, all_players, espn_to_sleeper, workspace):
    report = [f"## Week {week} Matchup Suggestions", ""]
    
    try:
        matchup_data = provider.get_user_matchup(league_id, user_id, week)
    except Exception as e:
        return [f"Could not load data for week {week}: {e}"]
        
    user_matchup = matchup_data["user"]
    opponent_matchup = matchup_data["opponent"]
    
    if not opponent_matchup:
        report.append(f"No opponent found for week {week}. (Bye week?)")
        return report

    fallback_metadata = provider.get_player_fallback_metadata() if hasattr(provider, 'get_player_fallback_metadata') else {}

    if platform == "espn":
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

    user_starters = [pid for pid in user_matchup.get("starters", []) if pid != "0"]
    user_players = user_matchup.get("players", [])
    user_bench = [pid for pid in user_players if pid not in user_starters]
    
    opponent_starters = [pid for pid in opponent_matchup.get("starters", []) if pid != "0"]

    healthy_bench_options = []
    for pid in user_bench:
        p = all_players.get(pid, {})
        name = _get_player_name(all_players, pid)
        pos, team = _get_player_pos_team(all_players, pid)
        if team and NFL_BYE_WEEKS_2026.get(team) != week and str(p.get("injury_status") or "").lower() not in ("out", "ir", "doubtful"):
            healthy_bench_options.append((name, pos, team))
    
    issues = []
    for pid in user_starters:
        p = all_players.get(pid, {})
        name = _get_player_name(all_players, pid)
        pos, team = _get_player_pos_team(all_players, pid)
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
            issues.append(f"- **{name}** ({pos} - {team}): {', '.join(flags)}")
            
    report.append("### Your Starter Issues")
    if issues:
        report.extend(issues)
        report.append("")
        report.append("### Start/Sit Recommendations")
        report.append("- Sit the flagged starters above unless their status improves before kickoff.")
        if healthy_bench_options:
            report.append("")
            report.append("#### Bench Alternatives")
            for name, pos, team in healthy_bench_options:
                report.append(f"- **{name}** ({pos} - {team}) - Healthy")
        else:
            report.append("- No healthy bench alternatives are available right now.")
    else:
        report.append("No immediate red flags (byes/injuries) found among your starters.")
        report.extend([
            "",
            "### Start/Sit Recommendations",
            "- Start your current lineup this week; no bye-week or injury-driven swaps are needed right now.",
        ])
        
    report.extend(["", "### Opponent's Starters"])
    for pid in opponent_starters:
        p = all_players.get(pid, {})
        name = _get_player_name(all_players, pid)
        pos, team = _get_player_pos_team(all_players, pid)
        injury = p.get("injury_status")
        flag = f" (Injury: {injury})" if injury and injury.lower() in ("out", "questionable", "doubtful") else ""
        report.append(f"- **{name}** ({pos} - {team}){flag}")
        
    # Waiver Suggestions
    report.extend(["", "### Waiver Targets (Trending Players)"])
    
    try:
        rostered = provider.get_all_rostered_players(league_id)
        if platform == "espn":
            rostered_sleeper = set()
            for pid in rostered:
                if str(pid) in espn_to_sleeper:
                    rostered_sleeper.add(espn_to_sleeper[str(pid)])
            rostered = rostered_sleeper
            
        # Try to fetch fresh trending, fallback to snapshot
        try:
            trending_players = fetch_sleeper_trending.fetch_trending("add", lookback_hours=24)
        except Exception:
            snapshot_path = latest_trending_snapshot(workspace)
            if snapshot_path:
                trending_players = load_trending(snapshot_path)
            else:
                trending_players = []
                
        suggested_count = 0
        for tp in trending_players:
            pid = str(tp.get("player_id"))
            if pid not in rostered:
                name = _get_player_name(all_players, pid)
                pos, team = _get_player_pos_team(all_players, pid)
                adds = tp.get("count", 0)
                report.append(f"- **{name}** ({pos} - {team}) - {adds} recent adds")
                suggested_count += 1
                if suggested_count >= 5:
                    break
                    
        if suggested_count == 0:
            report.append("- No obvious trending free agents found.")
    except Exception as e:
        report.append(f"- Could not generate waiver suggestions: {e}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("."))
    parser.add_argument("--week", type=int, help="Override the NFL week")
    parser.add_argument("--platform", type=str, default="sleeper", choices=["sleeper", "espn"])
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

    print("Fetching latest Sleeper player data...")
    raw_payload = fetch_sleeper_players.fetch_players()
    retrieved_at = datetime.now(timezone.utc)
    snapshot_path = fetch_sleeper_players.save_snapshot(raw_payload, workspace / "state", retrieved_at)
    all_players_list = load_players(snapshot_path)
    all_players = {str(p.get("player_id")): p for p in all_players_list}
    espn_to_sleeper = {str(p.get("espn_id")): str(p.get("player_id")) for p in all_players_list if p.get("espn_id")}

    report_lines = [f"# Game Week Report - Week {week}"]
    
    print(f"Analyzing Week {week - 1}...")
    prev_report = analyze_previous_week(provider, platform, league_id, user_id, week - 1, all_players, espn_to_sleeper)
    report_lines.extend([""] + prev_report)
    
    print(f"Generating suggestions for Week {week}...")
    next_report = analyze_next_week(provider, platform, league_id, user_id, week, all_players, espn_to_sleeper, workspace)
    report_lines.extend([""] + next_report)

    report_path = workspace / "game_week_report.md"
    report_text = "\n".join(report_lines)
    report_path.write_text(report_text, encoding="utf-8")
    
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(report_text + "\n")
            
    print(f"Report written to {report_path.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
