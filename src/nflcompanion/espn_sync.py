import json
from pathlib import Path
from datetime import datetime, timezone

from .config import ensure_espn_config
from .providers import get_provider

def sync_espn_data(workspace_root: Path, limit: int = 100) -> dict:
    config = ensure_espn_config(workspace_root)
    
    if "espn_league_id" not in config or "espn_team_id" not in config:
        raise ValueError("Missing espn_league_id or espn_team_id in config.")

    league_id = str(config["espn_league_id"])
    team_id = str(config["espn_team_id"])
    
    provider = get_provider("espn", config)
    
    # 1. Roster
    roster = provider.get_user_roster(league_id, team_id)
    
    # 2. Matchup
    try:
        # get current week
        state = provider.get_nfl_state()
        current_week = state.get("leg", 1)
        matchup = provider.get_user_matchup(league_id, team_id, current_week)
    except Exception as e:
        matchup = None

    # 3. Free Agents
    free_agents = provider.get_free_agents(league_id, limit=limit)

    sync_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "league_id": league_id,
        "team_id": team_id,
        "roster": roster,
        "matchup": matchup,
        "free_agents": free_agents
    }

    out_dir = workspace_root / "state" / "espn"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "espn_sync_state.json"
    
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(sync_data, f, indent=2)

    return sync_data
