# Draft companion state

This directory is the durable, inspectable state boundary for the draft
companion. Provider snapshots are immutable; later fetches create new files.

- `players/raw/`: complete provider responses, never hand-edited.
- `players/*.md`: provenance manifests for raw snapshots.
- `players/trending/raw/`: dated Sleeper add/drop trending snapshots. A new
  snapshot is written on every fetch (including automatically at the start of
  every agent session) because trending activity changes constantly; older
  snapshots are preserved.
- `players/trending/*.md`: provenance manifests for trending snapshots.
- `strategies/strategies.json`: draft strategy sets grouped by league and season,
  including session draft style (`sleeper_dynasty` or `espn_snake`) and ESPN
  reverse-round mode when relevant. Each saved strategy record includes
  `created_at`, `agent_rating`, `in_effect`, and pointers into the matching
  draft-context bucket (`draft-context/sleeper_dynasty/` or
  `draft-context/espn_snake/`) plus the append-only creation log under each
  bucket's `logs/strategy-creation-log.jsonl`.
- `leagues/`, `rosters/`, and `drafts/`: user decisions and append-only draft
  state to be added next.

Temporary canvas query examples:

```text
python scripts/query_players.py --name "McCaffrey" --limit 3
python scripts/query_players.py --position WR --active-only
python scripts/query_trending_players.py --direction add --limit 10
python scripts/query_trending_players.py --direction drop --position RB
```

The `sleeper-player-data` project extension uses the same state directory. Its
agent tool and canvas report `retrieved_at` from the selected snapshot's
filesystem update time and preserve older snapshots when a refresh creates a
new dated file.

The extension also registers an `onSessionStart` hook that fetches a fresh
Sleeper trending add/drop snapshot every time an agent session starts (or
resumes) and adds a summary of the top trending players as hidden context, so
draft-strategy and mock-draft conversations automatically see current
add/drop activity. The `sleeper_query_trending_players` tool lets an agent
query that local snapshot directly with the same filters as
`query_trending_players.py`.

Draft-strategy creation now uses a shared three-role workflow:

1. an interviewer agent captures questionnaire answers;
2. a validator agent checks for obvious player-data mistakes such as early
   kicker/defense plans;
3. a writer agent updates the Markdown strategy file and appends the creation
   transcript to the durable log so future mock drafts can review the outcome.
