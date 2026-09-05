# Copilot instructions

- Review `PLAN.md` before making implementation changes.
- When changing files under `src/`, `scripts/fetch_sleeper_players.py`,
  `scripts/query_players.py`, or `pyproject.toml`, update `PLAN.md` in the same
  change.
- Install the package with `python -m pip install -e .` before running tests.
- Run tests with `python -m unittest discover -s tests -v`.
- Keep generated player snapshots under `state/players/` out of commits.
