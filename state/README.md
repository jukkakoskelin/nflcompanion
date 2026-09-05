# Draft companion state

This directory is the durable, inspectable state boundary for the draft
companion. Provider snapshots are immutable; later fetches create new files.

- `players/raw/`: complete provider responses, never hand-edited.
- `players/*.md`: provenance manifests for raw snapshots.
- `strategies/strategies.json`: draft strategy sets grouped by league and season,
  including session draft style (`sleeper_dynasty` or `espn_snake`) and ESPN
  reverse-round mode when relevant. Each saved strategy record includes
  `created_at` as a UTC ISO-8601 timestamp.
- `leagues/`, `rosters/`, and `drafts/`: user decisions and append-only draft
  state to be added next.

Temporary canvas query examples:

```text
python scripts/query_players.py --name "McCaffrey" --limit 3
python scripts/query_players.py --position WR --active-only
```

The `sleeper-player-data` project extension uses the same state directory. Its
agent tool and canvas report `retrieved_at` from the selected snapshot's
filesystem update time and preserve older snapshots when a refresh creates a
new dated file.
