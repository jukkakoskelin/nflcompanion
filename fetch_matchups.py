#!/usr/bin/env python3
"""Fetch Sleeper matchups directly"""
import json
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider

config = load_config(Path('.'))
config['dynasty_league_id'] = '1392686219481079808'
config['sleeper_user_id'] = '1400795518526889984'

provider = get_provider('sleeper', config)

# Get matchups directly
league_id = '1392686219481079808'
matchups_w2 = provider.get_matchups(league_id, 2)

print("=== WEEK 2 MATCHUPS ===\n")
for m in matchups_w2:
    print(json.dumps(m, indent=2))
    print("\n" + "="*70 + "\n")

# Also get rosters
print("\n=== ALL ROSTERS ===\n")
rosters = provider.get_league_rosters(league_id)
for r in rosters:
    print(f"Roster {r.get('roster_id')}: Owner {r.get('owner_id')} - {r.get('display_name')} - {len(r.get('players', []))} players")
