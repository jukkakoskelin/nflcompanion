#!/usr/bin/env python3
"""Analyze Sleeper Dynasty Startup and Week 2 Matchup"""
import json
from pathlib import Path

# Load latest Sleeper player data
latest_raw = max(
    Path('state/players/raw').glob('sleeper-players-*.json'),
    key=lambda p: p.stat().st_mtime
)

with open(latest_raw) as f:
    raw_data = json.load(f)

# Create player lookup by ID
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

# Load roster state
roster_file = Path('state/rosters/sleeper_dynasty_1392686219481079808_state.json')
with open(roster_file) as f:
    your_roster_players = json.load(f)

print("=== YOUR SLEEPER DYNASTY ROSTER (Week 2) ===\n")

# Categorize players by likely starter status
likely_starters = []
bench_rb = []
bench_wr = []
bench_other = []

for pid, pdata in your_roster_players.items():
    sdata = players_by_id.get(pid, {})
    pos = sdata.get('position')
    name = sdata.get('name')
    team = sdata.get('team')
    injury = sdata.get('status')
    depth = sdata.get('depth') or 99
    
    player_obj = {
        'id': pid,
        'name': name,
        'pos': pos,
        'team': team,
        'injury': injury,
        'depth': depth
    }
    
    # Categorize based on position and depth chart
    if pos == 'QB':
        likely_starters.append(player_obj)
    elif pos == 'RB':
        if depth <= 2:
            likely_starters.append(player_obj)
        else:
            bench_rb.append(player_obj)
    elif pos == 'WR':
        if depth <= 2:
            likely_starters.append(player_obj)
        else:
            bench_wr.append(player_obj)
    elif pos == 'TE':
        if depth <= 2:
            likely_starters.append(player_obj)
        else:
            bench_other.append(player_obj)
    elif pos in ['K', 'DEF']:
        likely_starters.append(player_obj)
    else:
        bench_other.append(player_obj)

# Display starters
print("LIKELY STARTERS (11 player lineup):")
print("-" * 70)
starters_by_pos = {}
for p in likely_starters:
    pos = p['pos']
    if pos not in starters_by_pos:
        starters_by_pos[pos] = []
    starters_by_pos[pos].append(p)

for pos in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
    for p in sorted(starters_by_pos.get(pos, []), key=lambda x: x['depth']):
        injury_flag = f" [{p['injury']}]" if p['injury'] else ""
        team_str = (p['team'] or '?').ljust(3)
        print(f"  {(p['pos'] or '?'):3} {(p['name'] or 'Unknown'):28} ({team_str}){injury_flag}")

print("\nBENCH (Top Candidates):")
print("-" * 70)
print("\nBench RBs:")
for p in sorted(bench_rb, key=lambda x: x['depth'])[:8]:
    injury_flag = f" [{p['injury']}]" if p['injury'] else ""
    team_str = (p['team'] or '?').ljust(3)
    print(f"  {(p['pos'] or '?'):3} {(p['name'] or 'Unknown'):28} ({team_str}){injury_flag}")

print("\nBench WRs:")
for p in sorted(bench_wr, key=lambda x: x['depth'])[:8]:
    injury_flag = f" [{p['injury']}]" if p['injury'] else ""
    team_str = (p['team'] or '?').ljust(3)
    print(f"  {(p['pos'] or '?'):3} {(p['name'] or 'Unknown'):28} ({team_str}){injury_flag}")

print("\nBench Others:")
for p in sorted(bench_other, key=lambda x: x['depth'])[:5]:
    injury_flag = f" [{p['injury']}]" if p['injury'] else ""
    team_str = (p['team'] or '?').ljust(3)
    print(f"  {(p['pos'] or '?'):3} {(p['name'] or 'Unknown'):28} ({team_str}){injury_flag}")

print(f"\n\nTotal roster size: {len(your_roster_players)} players")
print("\n=== WEEK 1 RESULTS ===")
print("Your score: 157.58 points")
print("Opponent score: 179.18 points")
print("Result: LOSS by 21.60 points")

print("\n=== INJURY CONCERNS FOR WEEK 2 ===")
injuries = [p for p in likely_starters if p['injury'] and p['injury'].lower() in ['out', 'ir', 'doubtful', 'questionable']]
if injuries:
    print("Starters with concerns:")
    for p in injuries:
        print(f"  - {p['name']} ({p['pos']}, {p['team']}): {p['injury']}")
else:
    print("No major injuries among likely starters.")
