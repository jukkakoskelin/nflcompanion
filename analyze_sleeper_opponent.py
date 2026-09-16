#!/usr/bin/env python3
"""Analyze Sleeper Opponent Roster"""
import json
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider

config = load_config(Path('.'))
config['dynasty_league_id'] = '1392686219481079808'
config['sleeper_user_id'] = '1400795518526889984'

provider = get_provider('sleeper', config)

# Load player data
latest_raw = max(
    Path('state/players/raw').glob('sleeper-players-*.json'),
    key=lambda p: p.stat().st_mtime
)

with open(latest_raw) as f:
    raw_data = json.load(f)

# Create player lookup
players_by_id = {}
for player_id, player_data in raw_data.items():
    first_name = player_data.get('first_name', '').strip()
    last_name = player_data.get('last_name', '').strip()
    full_name = f"{first_name} {last_name}".strip()
    
    players_by_id[player_id] = {
        'name': full_name or f'Player {player_id}',
        'position': player_data.get('position'),
        'team': player_data.get('team'),
        'status': player_data.get('injury_status'),
        'depth': player_data.get('depth_chart_order', 99),
    }

# Get matchup
matchup = provider.get_user_matchup('1392686219481079808', '1400795518526889984', 2)

print(f"User Roster ID: {matchup.get('user_roster_id')}")
print(f"Opponent Roster ID: {matchup.get('opponent_roster_id')}\n")

# Get all rosters
rosters = provider.get_league_rosters('1392686219481079808')
rosters_by_id = {r.get('roster_id'): r for r in rosters}

print(f"=== OPPONENT ROSTER (Roster {matchup.get('opponent_roster_id')}) ===\n")

opponent_roster = rosters_by_id.get(matchup.get('opponent_roster_id'), {})
opponent_owner = opponent_roster.get('display_name', 'Unknown')
opponent_players = opponent_roster.get('players', [])

print(f"Owner: {opponent_owner}")
print(f"Total Players: {len(opponent_players)}\n")

# Categorize opponent's starters
opponent_starters = []
opponent_bench_rb = []
opponent_bench_wr = []
opponent_bench_other = []

for pid in opponent_players:
    pid_str = str(pid)
    sdata = players_by_id.get(pid_str, {})
    pos = sdata.get('position')
    name = sdata.get('name')
    team = sdata.get('team')
    injury = sdata.get('status')
    depth = sdata.get('depth') or 99
    
    player_obj = {
        'id': pid_str,
        'name': name,
        'pos': pos,
        'team': team,
        'injury': injury,
        'depth': depth
    }
    
    # Categorize
    if pos == 'QB':
        opponent_starters.append(player_obj)
    elif pos == 'RB':
        if depth <= 2:
            opponent_starters.append(player_obj)
        else:
            opponent_bench_rb.append(player_obj)
    elif pos == 'WR':
        if depth <= 2:
            opponent_starters.append(player_obj)
        else:
            opponent_bench_wr.append(player_obj)
    elif pos == 'TE':
        if depth <= 2:
            opponent_starters.append(player_obj)
        else:
            opponent_bench_other.append(player_obj)
    elif pos in ['K', 'DEF']:
        opponent_starters.append(player_obj)
    else:
        opponent_bench_other.append(player_obj)

print("LIKELY STARTERS:")
print("-" * 70)
starters_by_pos = {}
for p in opponent_starters:
    pos = p['pos']
    if pos not in starters_by_pos:
        starters_by_pos[pos] = []
    starters_by_pos[pos].append(p)

for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
    for p in sorted(starters_by_pos.get(pos, []), key=lambda x: x['depth']):
        injury_flag = f" [{p['injury']}]" if p['injury'] else ""
        team_str = (p['team'] or '?').ljust(3)
        print(f"  {(p['pos'] or '?'):3} {(p['name'] or 'Unknown'):28} ({team_str}){injury_flag}")

print("\n" + "="*70)
print("\n=== MATCHUP ANALYSIS ===")
print("Your Week 1 Score: 157.58")
print("Week 1 Opponent (Roster 1) Score: 179.18")
print("Difference: -21.60 (LOSS)")
print("\nWeek 2 Opponent: Roster 7")
print(f"Owner: {opponent_owner}")
print(f"Week 2 Projected Matchup Status: Awaiting live scoring\n")
