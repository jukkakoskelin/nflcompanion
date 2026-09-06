# Copilot instructions

- Review `PLAN.md` before making implementation changes.
- When changing files under `src/`, `scripts/fetch_sleeper_players.py`,
  `scripts/query_players.py`, `scripts/fetch_sleeper_trending.py`,
  `scripts/query_trending_players.py`, or `pyproject.toml`, update `PLAN.md` in
  the same change.
- Install the package with `python -m pip install -e .` before running tests.
- Run tests with `python -m unittest discover -s tests -v`.
- Keep generated player snapshots under `state/players/` out of commits.
- Never record or commit a draft pick without explicit user instruction. When the user explicitly states their pick (e.g. 'Picked X' or 'Take Y'), record it immediately without asking for a secondary confirmation.
- Refer to `AGENTS.md` for shared repository-wide guidelines.

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

## Live draft companion

- Execute all draft state interactions through native MCP tools (`draft_get_session`, `draft_init_session`, `draft_recommend_candidates`, `draft_record_pick`, `draft_record_observed_pick`, `draft_next_pick_preview`, `draft_update_strategy`, `draft_sync_sleeper_picks`) rather than running shell scripts.
- Keep recommendation responses fast and bounded to the requested candidates
  within the 15-second budget (targeting <5s from local data).
- Ranks are deterministic; synthesize and explain factor scores without inventing
  rankings or certainty.
- When the user states who they picked or want to pick, record it immediately via `draft_record_pick` (`confirmed: true`). Do not prompt for an extra confirmation round-trip. Never record unconfirmed picks merely because they were recommended.

