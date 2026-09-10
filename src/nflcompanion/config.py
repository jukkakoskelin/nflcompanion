import json
import os
from getpass import getpass
from pathlib import Path
from typing import Any

def load_config(workspace_root: Path) -> dict[str, Any]:
    config_path = workspace_root / "state" / "config.json"
    if not config_path.exists():
        legacy_path = workspace_root / "state" / "sleeper_user_info.json"
        if legacy_path.exists():
            data = json.loads(legacy_path.read_text(encoding="utf-8"))
            return {
                "dynasty_league_id": data.get("league_id"),
                "sleeper_user_id": data.get("user_id")
            }
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))

def save_config(workspace_root: Path, config: dict[str, Any]) -> None:
    config_path = workspace_root / "state" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")

def ensure_espn_config(workspace_root: Path) -> dict[str, Any]:
    config = load_config(workspace_root)
    updated = False
    
    if "espn_league_id" not in config:
        config["espn_league_id"] = input("Enter ESPN League ID: ").strip()
        updated = True
    if "espn_team_id" not in config:
        config["espn_team_id"] = input("Enter ESPN Team ID: ").strip()
        updated = True
    if "espn_year" not in config:
        year_input = input("Enter ESPN Year (e.g. 2026): ").strip()
        config["espn_year"] = int(year_input) if year_input else 2026
        updated = True
    espn_s2 = os.getenv("NFLCOMPANION_ESPN_S2") or os.getenv("ESPN_S2") or config.get("espn_s2")
    if not espn_s2:
        espn_s2 = getpass("Enter ESPN espn_s2 cookie (input hidden): ").strip()
    swid = os.getenv("NFLCOMPANION_SWID") or os.getenv("SWID") or config.get("swid")
    if not swid:
        swid = getpass("Enter ESPN swid cookie (input hidden): ").strip()
    if espn_s2:
        config["espn_s2"] = espn_s2
    if swid:
        config["swid"] = swid
        
    if updated:
        save_config(
            workspace_root,
            {k: v for k, v in config.items() if k not in {"espn_s2", "swid"}},
        )
        
    return config
