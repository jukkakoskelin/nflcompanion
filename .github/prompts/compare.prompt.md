---
description: Quick projected comparison of my current or next matchweek matchup
---

Give a quick comparison of my fantasy matchup for the current or next NFL week.

1. Run `python scripts/suggest_starters.py` from the repository root. It determines the NFL week from the league state, refreshes player data, and writes `weekly_matchup_suggestion.md`.
2. Decide which week applies:
   - If the matchup for the current week has already been scored (games have started or finished), the earlier week has ended and the comparison should be for the next week. Re-run with `--week <next week>`.
   - Otherwise use the current week.
3. Read the generated report and summarize in a short table: my starters vs. opponent starters, projected totals, and the position-by-position edge.
4. List any starter issues (injuries, byes, inactive status) from the report in one line each.

Keep the answer under about 20 lines. Cite only numbers that appear in the report; do not invent projections.
