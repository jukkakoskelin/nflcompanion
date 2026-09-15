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

## GitHub issue-driven feature workflow

- Treat feature development as an issue-driven lifecycle with strict branch isolation: Intake -> Branching -> Planning -> Implementation -> Review -> PR Creation.
- Never make changes to `PLAN.md`, source code, or tests directly on `main`. Always create a feature branch named `feature/<issue_id>-<sanitized-title>` via `python scripts/issue_workflow.py start <issue_id>` before beginning work.
- If no issue exists, search existing open issues or guide the user to create one using `.github/ISSUE_TEMPLATE/feature_request.md` (`python scripts/issue_workflow.py create-issue ...`).
- **Planning Agent**: Reads the issue, evaluates the Expected End Result (adopting and expanding it if present, or defining an objective Definition of Done if missing), and records it in `PLAN.md`.
- **Implementor Agent**: Implements the feature and creates automated tests specifically verifying that the Expected End Result has been achieved. Ensures `python -m unittest discover -s tests -v` passes.
- **Reviewer Agent**: Reviews code and markdown quality, security, adherence to the plan, and test outcomes.
- **PR Creation**: Push the branch and submit the Pull Request using `python scripts/issue_workflow.py pr <issue_id> ...` which populates `.github/pull_request_template.md`. The `.github/workflows/pr-synopsis.yml` workflow will automatically run CI and publish a human reviewer synopsis on the PR.


