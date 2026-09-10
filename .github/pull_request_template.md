## Description

<!-- Describe the rationale and details of the changes made in this pull request -->

## Guardrails Checklist

Please ensure the following guardrails from `AGENTS.md` have been met before submitting:

- [ ] **Agent Guidelines:** I have reviewed `PLAN.md` and `AGENTS.md` before making implementation changes.
- [ ] **Plan Updates:** If I modified files under `src/`, key scripts (e.g., `scripts/fetch_sleeper_players.py`), or `pyproject.toml`, I have updated `PLAN.md` in this same commit/change.
- [ ] **Status Line:** If `PLAN.md` was updated, I ensured the `Status:` line was preserved or updated.
- [ ] **Tests Passing:** I have installed the package (`python -m pip install -e .`) and run tests (`python -m unittest discover -s tests -v`) locally.
- [ ] **State Isolation:** I have ensured no generated player snapshots under `state/players/` are included in these commits.
