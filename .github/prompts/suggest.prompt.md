---
description: Suggest players to pick up or trade for from waivers based on trending adds
---

Suggest waiver-wire moves for my team.

1. Make sure the data is fresh: run `python scripts/fetch_sleeper_trending.py` and `python scripts/fetch_sleeper_players.py` from the repository root, or use the `sleeper_query_trending_players` tool if the snapshot is recent enough.
2. Get the top trending adds with `python scripts/query_trending_players.py --direction add --limit 25`. Filter by position if the user asked for one (`--position RB|WR|TE|QB`).
3. Identify my roster weak spots from the latest matchup report (`weekly_matchup_suggestion.md`) or by running `python scripts/game_week_report.py` if the report is missing. Note bench players who are healthy and could be trade or drop candidates.
4. Output up to 5 suggestions as a table: player (pos, team), trending add count, reason (roster need or upside), and a suggested drop candidate from my bench.

Rules:
- Use only local snapshot data and tool output. Do not invent player data, stats, or ranking certainty.
- Give one-sentence rationales that cite the data.
- Do not record, add, or drop anything on the league; this command only suggests.
