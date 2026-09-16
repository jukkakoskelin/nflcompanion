#!/usr/bin/env python3
"""Get my roster ID and opponent roster ID for Week 2"""
import json
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider

config = load_config(Path('.'))
config['dynasty_league_id'] = '1392686219481079808'
config['sleeper_user_id'] = '1400795518526889984'

provider = get_provider('sleeper', config)

# Get rosters
rosters = provider.get_league_rosters('1392686219481079808')
print("MY ROSTER:")
for r in rosters:
    if str(r.get('owner_id')) == '1400795518526889984':
        print(f"  Roster ID: {r.get('roster_id')}")
        print(f"  Owner ID: {r.get('owner_id')}")
        print(f"  Owner Name: {r.get('display_name')}")
        print(f"  Players: {len(r.get('players', []))}")
        print(f"  Players: {r.get('players', [])}")
        my_roster_id = r.get('roster_id')
        break

# Get matchups
matchups = provider.get_matchups('1392686219481079808', 2)
print(f"\nWEEK 2 MATCHUPS: {len(matchups)} matchups")

for m in matchups:
    if m.get('roster_id') == my_roster_id:
        print(f"\nYOUR MATCHUP:")
        print(f"  Roster ID: {m.get('roster_id')}")
        print(f"  Matchup ID: {m.get('matchup_id')}")
        print(f"  Starters: {m.get('starters')}")
        
        # Find opponent
        matchup_id = m.get('matchup_id')
        for m2 in matchups:
            if m2.get('matchup_id') == matchup_id and m2.get('roster_id') != my_roster_id:
                print(f"\nOPPONENT MATCHUP:")
                print(f"  Roster ID: {m2.get('roster_id')}")
                print(f"  Starters: {m2.get('starters')}")
                
                # Get opponent roster details
                for r in rosters:
                    if r.get('roster_id') == m2.get('roster_id'):
                        print(f"  Owner Name: {r.get('display_name')}")
                        print(f"  Players: {r.get('players', [])}")
                break
        break
