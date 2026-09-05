# nflcompanion
NFL Fantasy draft companion agents

## Sleeper player state

The project extension `sleeper-player-data` provides two read-only agent tools:

- `sleeper_ensure_player_state` checks for the latest local snapshot and fetches
  the public Sleeper NFL player endpoint only when state is missing (or when
  `refresh` is requested).
- `sleeper_query_players` filters the local snapshot by name, position, team,
  and active status.

It also provides a canvas named **Sleeper player data** for interactive queries
and a **Fetch latest** button. Snapshots are stored under `state/players/` with
an ISO timestamp in each provenance manifest; generated JSON and manifests are
ignored by git and never belong in the remote repository.
