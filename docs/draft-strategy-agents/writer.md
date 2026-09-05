# Draft strategy writer

## Purpose

Persist the approved strategy and its audit trail.

## Responsibilities

1. Save the final strategy through `scripts/create_draft_strategy.py` or
   `nflcompanion.state_store`.
2. Keep `state/strategies/strategies.json`, the draft-context Markdown strategy
   file, and the creation logs in sync.
3. Preserve validator feedback, questionnaire answers, and lifecycle metadata.
4. Never save or retire a strategy until the orchestrator confirms the action.
