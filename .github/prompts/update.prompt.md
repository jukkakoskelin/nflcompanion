---
description: Pull the current player data and trending adds/drops from Sleeper
---

Refresh the local Sleeper data snapshots for this workspace.

1. Run the player snapshot fetch from the repository root:
   `python scripts/fetch_sleeper_players.py`
2. Run the trending fetch:
   `python scripts/fetch_sleeper_trending.py`
3. Report briefly: the snapshot file paths written under `state/`, the number of players, and the trending retrieval timestamp.

If a command fails, show the error and stop. Do not commit anything; snapshots under `state/players/` must stay out of commits.
