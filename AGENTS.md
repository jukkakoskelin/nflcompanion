# NFL Companion Agent Guidelines

- Review `PLAN.md` before proposing or making implementation changes.
- GUARDRAIL ENFORCEMENT: When changing files under `src/`, `scripts/fetch_sleeper_players.py`, `scripts/query_players.py`, `scripts/fetch_sleeper_trending.py`, `scripts/query_trending_players.py`, or `pyproject.toml`, you MUST update `PLAN.md` in the same commit/change. Ensure the `Status:` line is preserved or updated.
- Install the package with `python -m pip install -e .` before running tests.
- Run tests with `python -m unittest discover -s tests -v`.
- Keep generated player snapshots under `state/players/` out of commits.
- Never record or commit a draft pick without explicit user instruction. When the user explicitly states their pick (e.g. 'Picked X' or 'Take Y'), record it immediately without asking for a secondary confirmation.

## Draft Strategy Creation

- Treat draft-strategy work as a four-role flow: orchestrator, interviewer, validator, and writer (with evaluator as quality gate).
- Read the relevant league context from `draft-context/sleeper_dynasty/` or `draft-context/espn_snake/` before proposing a strategy.
- Persist final strategies through `scripts/create_draft_strategy.py` or `nflcompanion.state_store` helpers so the Markdown strategy file and append-only creation log stay in sync.
- Validator feedback must call out obvious red flags such as early kicker or defense plans before the writer saves the strategy.
- Keep the tracked role contracts in `docs/draft-strategy-agents/*.md` aligned with the saved workflow metadata.

## Live Draft Companion

- All draft state interaction during live drafts and mock drafts must execute via native MCP tools (`draft_get_session`, `draft_init_session`, `draft_recommend_candidates`, `draft_record_pick`, `draft_record_observed_pick`, `draft_next_pick_preview`, `draft_update_strategy`, `draft_sync_sleeper_picks`). Do not invoke terminal/shell commands (`scripts/draft_companion.py`) during active sessions.
- Fast lane responses (candidate recommendations) must execute within a 15-second budget (targeting <5 seconds) using local snapshot data without blocking on network refreshes.
- Candidate scoring is deterministic; provide one-sentence rationales and cite local evidence.
- Do not invent player data or ranking certainty.
- When the user states who they picked or want to pick, record it immediately via `draft_record_pick` (`confirmed: true`). Do not prompt for an extra confirmation round-trip. Never record unconfirmed picks merely because they were recommended.

