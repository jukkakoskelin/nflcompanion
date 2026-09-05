---
name: draft-strategy
description: Use this skill when creating, reviewing, testing, or updating a fantasy football draft strategy for ESPN snake or Sleeper dynasty leagues.
---

# Fantasy Draft Strategy Workflow

This skill orchestrates the multi-agent strategy creation workflow to produce durable, user-approved Markdown draft strategies and append-only creation logs.

## The Five-Role Workflow

The strategy creation flow separates domain validation from workflow evaluation across five distinct roles:

1. **Orchestrator** ([docs/draft-strategy-agents/orchestrator.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/orchestrator.md)):
   - Reads league context from `draft-context/espn/`, `draft-context/espn_snake/`, or `draft-context/sleeper_dynasty/`.
   - Guides the questionnaire intake and routes answers to the validator and evaluator.
   - Prevents persistence until the user explicitly confirms the strategy.
2. **Interviewer** ([docs/draft-strategy-agents/interviewer.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/interviewer.md)):
   - Leads the user through the strategy questionnaire one question at a time (use the `ask_question` tool or interactive chat).
   - Core intake for ESPN 16-team snake:
     1. First-round anchor (RB, WR, or hero QB).
     2. Second-round complement.
     3. No-RB-in-first-two-rounds contingency (commit to two WRs + aggressive late-RB plan).
     4. QB timing (early elite vs. middle-tier starter).
     5. TE timing (early elite vs. middle-tier value).
3. **Strategy Agent** ([docs/draft-strategy-agents/espn-strategy-agent.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/espn-strategy-agent.md)):
   - Translates questionnaire responses into structured priorities, conditional pivots, early fades (avoid early K and DST), round plan, and 14-player roster target.
4. **Validator** ([docs/draft-strategy-agents/validator.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/validator.md)):
   - Checks football logic against league settings, scoring, and local player/trending snapshots.
   - Flags obvious red flags (e.g. early kicker or defense).
5. **Evaluator** ([docs/draft-strategy-agents/evaluator.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/evaluator.md)):
   - Quality gate verifying completeness, traceability, and resolution of validator warnings.
6. **Writer** ([docs/draft-strategy-agents/writer.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/writer.md)):
   - Persists the final approved strategy and creation log. Never overwrites existing strategy files.

## Subagent Delegation in Antigravity

When running interactively, the orchestrator can invoke or define subagents using `invoke_subagent` and `define_subagent`:

- Define `validator` with read tools to inspect `draft-context/` and `state/`.
- Define `evaluator` to score completeness and quality gates.
- Require explicit confirmation from the user before invoking the writer step.

## Non-Interactive / Script Execution

Strategies can be created or simulated programmatically:

```powershell
# Simulate an ESPN 16-team snake draft strategy:
python scripts/create_draft_strategy.py --league-id espn-16-2026-slot-9-3rr --season 2026 --draft-style espn_snake --reverse-round --simulate

# Persist an interactive session:
python scripts/create_draft_strategy.py --league-id espn-16-2026-slot-9-3rr --season 2026 --draft-style espn_snake --reverse-round --name "Hero RB with Early TE" --strategy-json '<json>' --questionnaire-json '<json>'
```
