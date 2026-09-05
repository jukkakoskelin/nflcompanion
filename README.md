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

## Draft strategy context

Draft strategies now persist in two places:

- `state/strategies/strategies.json` keeps the indexed session view keyed by
  league id and season.
- `draft-context/sleeper_dynasty/strategies/` and
  `draft-context/espn_snake/strategies/` keep the user-editable Markdown strategy
  files plus append-only creation logs under `logs/`.

Use `python scripts/create_draft_strategy.py --simulate ...` to generate a
sample strategy/log pair for non-interactive testing, or pass
`--strategy-json`/`--questionnaire-json` from an interactive Copilot chat flow
after the interviewer, validator, and writer agents agree on the final plan.
