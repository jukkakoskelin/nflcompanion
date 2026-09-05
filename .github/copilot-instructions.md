# Copilot instructions

- Review `PLAN.md` before making implementation changes.
- When changing files under `src/`, `scripts/fetch_sleeper_players.py`,
  `scripts/query_players.py`, `scripts/fetch_sleeper_trending.py`,
  `scripts/query_trending_players.py`, or `pyproject.toml`, update `PLAN.md` in
  the same change.
- Install the package with `python -m pip install -e .` before running tests.
- Run tests with `python -m unittest discover -s tests -v`.
- Keep generated player snapshots under `state/players/` out of commits.

## Draft strategy creation

- Treat draft-strategy work as a four-role flow: orchestrator, interviewer,
  validator, and writer.
- Read the relevant league context from `draft-context/sleeper_dynasty/` or
  `draft-context/espn_snake/` before proposing a strategy.
- Persist final strategies through `scripts/create_draft_strategy.py` or the
  matching `nflcompanion.state_store` helpers so the Markdown strategy file and
  append-only creation log stay in sync.
- Validator feedback must call out obvious red flags such as early kicker or
  defense plans before the writer saves the strategy.
- Keep the tracked role contracts in `docs/draft-strategy-agents/*.md` aligned
  with the saved workflow metadata.
