#!/usr/bin/env python3
"""Analyze Sleeper Dynasty Bench - Future Value & Keepers"""
import json
from pathlib import Path
from nflcompanion.config import load_config
from nflcompanion.providers import get_provider

config = load_config(Path('.'))
config['dynasty_league_id'] = '1392686219481079808'
config['sleeper_user_id'] = '1400795518526889984'

provider = get_provider('sleeper', config)

# Load player data with more detail
latest_raw = max(
    Path('state/players/raw').glob('sleeper-players-*.json'),
    key=lambda p: p.stat().st_mtime
)

with open(latest_raw) as f:
    raw_data = json.load(f)

# Create comprehensive player lookup
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
        'years_exp': player_data.get('years_exp'),  # Years of experience
        'nfl_debut_year': player_data.get('nfl_debut_year'),
        'age': player_data.get('age'),
        'rookie_year': player_data.get('rookie_year'),
    }

# Get rosters
rosters = provider.get_league_rosters('1392686219481079808')

# Find my roster
my_roster_id = 6
my_roster_players = [p for r in rosters if r.get('roster_id') == my_roster_id for p in r.get('players', [])]
my_starters = ['6904', '9509', '8150', '6786', '10229', '2133', '10859', '7594', '9756', '4046']

# Categorize bench
bench_players = [pid for pid in my_roster_players if str(pid) not in my_starters]

bench_data = {
    'rbs': [],
    'wrs': [],
    'tes': [],
    'qbs': [],
    'other': []
}

for pid in bench_players:
    pid_str = str(pid)
    p = players_by_id.get(pid_str, {})
    pos = p.get('position')
    
    player_obj = {
        'id': pid_str,
        'name': p.get('name'),
        'pos': pos,
        'team': p.get('team'),
        'status': p.get('status'),
        'depth': p.get('depth') or 99,
        'years_exp': p.get('years_exp'),
        'age': p.get('age'),
        'rookie_year': p.get('rookie_year'),
    }
    
    if pos == 'RB':
        bench_data['rbs'].append(player_obj)
    elif pos == 'WR':
        bench_data['wrs'].append(player_obj)
    elif pos == 'TE':
        bench_data['tes'].append(player_obj)
    elif pos == 'QB':
        bench_data['qbs'].append(player_obj)
    else:
        bench_data['other'].append(player_obj)

print("="*80)
print("SLEEPER DYNASTY BENCH ANALYSIS - FUTURE VALUE ASSESSMENT")
print("="*80)

def score_player_potential(p):
    """Score a player's potential value (higher = better to keep)"""
    score = 0
    factors = []
    
    # Age/Experience factors (most important for dynasty)
    years_exp = p.get('years_exp')
    if years_exp is not None:
        if years_exp <= 2:  # Very young (likely 1st-3rd year)
            score += 40
            factors.append("✓ Very young (1-3 years)")
        elif years_exp <= 4:
            score += 25
            factors.append("✓ Young (4-5 years)")
        elif years_exp >= 7:
            score -= 20
            factors.append("✗ Aging out")
    
    # Depth chart position (opportunity for growth)
    depth = p.get('depth') or 99
    if depth == 2:
        score += 15
        factors.append("✓ Backup (one injury away)")
    elif depth == 3:
        score += 10
        factors.append("• Deep bench but could emerge")
    elif depth >= 4:
        score -= 5
        factors.append("✗ Very deep, limited opportunity")
    
    # Position considerations
    pos = p.get('pos')
    if pos == 'RB':
        score += 5  # RBs have shorter shelf lives, younger is more valuable
        if depth <= 2:
            score += 10  # RB backups are valuable
    elif pos == 'WR':
        score += 0  # Neutral
        if depth <= 2:
            score += 8
    elif pos == 'TE':
        score += 10  # TEs develop later, young TEs are valuable assets
        if depth <= 2:
            score += 15
    elif pos == 'QB':
        score += 15  # Young QBs are extremely valuable in dynasty
        if depth == 1:
            score += 25
    
    return score, factors

# Analyze by position
print("\n" + "="*80)
print("RUNNING BACKS - BENCH ANALYSIS")
print("="*80)

for p in sorted(bench_data['rbs'], key=lambda x: x['depth']):
    score, factors = score_player_potential(p)
    injury_flag = f" [{p['status']}]" if p['status'] else ""
    age_info = f", Age {p['age']}" if p['age'] else ""
    exp_info = f", {p['years_exp']}yr exp" if p['years_exp'] is not None else ""
    
    print(f"\n{p['name']:28} ({p['team']}) Depth: {p['depth']}{age_info}{exp_info}{injury_flag}")
    print(f"  Potential Score: {score:+d}/100")
    
    if score >= 30:
        print(f"  ⭐ HOLD - Strong future value")
    elif score >= 15:
        print(f"  ✓ KEEP - Decent development potential")
    elif score >= 0:
        print(f"  ~ CONSIDER - Marginal value")
    else:
        print(f"  ✗ TRADEABLE - Limited upside")
    
    for factor in factors:
        print(f"    {factor}")

print("\n" + "="*80)
print("WIDE RECEIVERS - BENCH ANALYSIS")
print("="*80)

for p in sorted(bench_data['wrs'], key=lambda x: x['depth']):
    score, factors = score_player_potential(p)
    injury_flag = f" [{p['status']}]" if p['status'] else ""
    age_info = f", Age {p['age']}" if p['age'] else ""
    exp_info = f", {p['years_exp']}yr exp" if p['years_exp'] is not None else ""
    
    print(f"\n{p['name']:28} ({p['team']}) Depth: {p['depth']}{age_info}{exp_info}{injury_flag}")
    print(f"  Potential Score: {score:+d}/100")
    
    if score >= 30:
        print(f"  ⭐ HOLD - Strong future value")
    elif score >= 15:
        print(f"  ✓ KEEP - Decent development potential")
    elif score >= 0:
        print(f"  ~ CONSIDER - Marginal value")
    else:
        print(f"  ✗ TRADEABLE - Limited upside")
    
    for factor in factors:
        print(f"    {factor}")

print("\n" + "="*80)
print("TIGHT ENDS - BENCH ANALYSIS")
print("="*80)

for p in sorted(bench_data['tes'], key=lambda x: x['depth']):
    score, factors = score_player_potential(p)
    injury_flag = f" [{p['status']}]" if p['status'] else ""
    age_info = f", Age {p['age']}" if p['age'] else ""
    exp_info = f", {p['years_exp']}yr exp" if p['years_exp'] is not None else ""
    
    print(f"\n{p['name']:28} ({p['team']}) Depth: {p['depth']}{age_info}{exp_info}{injury_flag}")
    print(f"  Potential Score: {score:+d}/100")
    
    if score >= 30:
        print(f"  ⭐ HOLD - Strong future value")
    elif score >= 15:
        print(f"  ✓ KEEP - Decent development potential")
    elif score >= 0:
        print(f"  ~ CONSIDER - Marginal value")
    else:
        print(f"  ✗ TRADEABLE - Limited upside")
    
    for factor in factors:
        print(f"    {factor}")

print("\n" + "="*80)
print("QUARTERBACKS - BENCH ANALYSIS")
print("="*80)

for p in sorted(bench_data['qbs'], key=lambda x: x['depth']):
    score, factors = score_player_potential(p)
    age_info = f", Age {p['age']}" if p['age'] else ""
    exp_info = f", {p['years_exp']}yr exp" if p['years_exp'] is not None else ""
    
    print(f"\n{p['name']:28} ({p['team']}) Depth: {p['depth']}{age_info}{exp_info}")
    print(f"  Potential Score: {score:+d}/100")
    
    if score >= 30:
        print(f"  ⭐ HOLD - Strong future value")
    elif score >= 15:
        print(f"  ✓ KEEP - Decent development potential")
    elif score >= 0:
        print(f"  ~ CONSIDER - Marginal value")
    else:
        print(f"  ✗ TRADEABLE - Limited upside")
    
    for factor in factors:
        print(f"    {factor}")

print("\n" + "="*80)
print("SUMMARY: BENCH PLAYERS TO NEVER SELL")
print("="*80)

# Find all high-value keepers
keepers = []
for category in ['rbs', 'wrs', 'tes', 'qbs']:
    for p in bench_data[category]:
        score, _ = score_player_potential(p)
        if score >= 30:
            keepers.append((p['name'], p['pos'], p['team'], p['depth'], score))

if keepers:
    print("\n⭐ TOP DYNASTY ASSETS (High Future Value):\n")
    for name, pos, team, depth, score in sorted(keepers, key=lambda x: -x[4]):
        print(f"  {name:28} ({pos}, {team}) - Depth: {depth} - Score: {score:+d}")
else:
    print("\nNo players currently have extremely high future value scores.")
    print("Check your taxi squad for young talent there!")

print("\n" + "="*80)
