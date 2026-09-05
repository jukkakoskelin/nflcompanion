# Draft companion state

This directory is the durable, inspectable state boundary for the draft
companion. Provider snapshots are immutable; later fetches create new files.

- `players/raw/`: complete provider responses, never hand-edited.
- `players/*.md`: provenance manifests for raw snapshots.
- `leagues/`, `strategies/`, `rosters/`, and `drafts/`: user decisions and
  append-only draft state to be added next.

Temporary canvas query examples:

```text
python scripts/query_players.py --name "McCaffrey" --limit 3
python scripts/query_players.py --position WR --active-only
```
