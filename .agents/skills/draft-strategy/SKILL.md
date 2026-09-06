---
name: draft-strategy
description: Use this skill when creating, reviewing, testing, or updating a fantasy football draft strategy for ESPN snake or Sleeper dynasty leagues.
---

# Fantasy Draft Strategy Workflow

This skill orchestrates the multi-agent strategy creation workflow to produce durable, user-approved Markdown draft strategies and append-only creation logs.

## Choosing the Platform

At the start of every strategy session, ask the user which format they are drafting for:
- **ESPN 16-team snake** → route through `espn-snake-strategy-agent` ([docs/draft-strategy-agents/espn-strategy-agent.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/espn-strategy-agent.md))
- **Sleeper 10-team dynasty** → route through `sleeper-dynasty-strategy-agent` ([docs/draft-strategy-agents/sleeper-dynasty-strategy-agent.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/sleeper-dynasty-strategy-agent.md))

Read the corresponding strategy agent file before beginning the questionnaire.

## The Five-Role Workflow

The strategy creation flow separates domain validation from workflow evaluation across five distinct roles:

1. **Orchestrator** ([docs/draft-strategy-agents/orchestrator.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/orchestrator.md)):
   - Reads league context from `draft-context/espn/`, `draft-context/espn_snake/`, or `draft-context/sleeper_dynasty/`.
   - Determines the platform (ESPN or Sleeper) and routes to the correct strategy agent.
   - Guides the questionnaire intake and routes answers to the validator and evaluator.
   - Prevents persistence until the user explicitly confirms the strategy.
2. **Interviewer** ([docs/draft-strategy-agents/interviewer.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/interviewer.md)):
   - Leads the user through the strategy questionnaire one question at a time (use the `ask_question` tool or interactive chat).
   - **ESPN 16-team snake intake:**
     1. First-round anchor (RB, WR, or hero QB).
     2. Second-round complement.
     3. No-RB-in-first-two-rounds contingency (commit to two WRs + aggressive late-RB plan).
     4. QB timing (early elite vs. middle-tier starter).
     5. TE timing (early elite vs. middle-tier value).
   - **Sleeper Dynasty 10-team startup snake intake:**
     1. First-round anchor (elite WR, hero QB/Superflex, or elite RB).
     2. Superflex QB timing (two QBs in rounds 1–3, or stagger to rounds 4–6).
     3. TE timing (elite early rounds 2–4 vs. later value).
     4. Dynasty horizon (win-now vs. rebuild vs. balanced).
     5. Taxi squad philosophy (rookie hoarding vs. production-ready preference).
     6. Draft slot (if known — can be deferred until draft starts as TBD).
3. **Strategy Agent** (style-specific):
   - **ESPN:** [docs/draft-strategy-agents/espn-strategy-agent.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/espn-strategy-agent.md) — translates questionnaire into anchor, second-round complement, QB/TE plans, and 14-player roster target.
   - **Sleeper Dynasty:** [docs/draft-strategy-agents/sleeper-dynasty-strategy-agent.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/sleeper-dynasty-strategy-agent.md) — translates questionnaire into anchor, Superflex QB plan, TE plan, dynasty horizon, taxi-squad plan, and 25-player active roster target.
4. **Validator** ([docs/draft-strategy-agents/validator.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/validator.md)):
   - Checks football logic against league settings, scoring, and local player/trending snapshots.
   - Flags obvious red flags (e.g. early kicker or defense, single-QB plan in Superflex).
5. **Evaluator** ([docs/draft-strategy-agents/evaluator.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/evaluator.md)):
   - Quality gate verifying completeness, traceability, and resolution of validator warnings.
6. **Writer** ([docs/draft-strategy-agents/writer.md](file:///d:/repos/nflcompanion/docs/draft-strategy-agents/writer.md)):
   - Persists the final approved strategy and creation log. Never overwrites existing strategy files.
   - **ESPN:** saves to `draft-context/espn_snake/strategies/` and `draft-context/espn_snake/logs/`.
   - **Sleeper Dynasty:** saves to `draft-context/sleeper_dynasty/strategies/` and `draft-context/sleeper_dynasty/logs/`.

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

# Persist an interactive ESPN session:
python scripts/create_draft_strategy.py --league-id espn-16-2026-slot-9-3rr --season 2026 --draft-style espn_snake --reverse-round --name "Hero RB with Early TE" --strategy-json '<json>' --questionnaire-json '<json>'

# Simulate a Sleeper 10-team dynasty startup strategy:
python scripts/create_draft_strategy.py --league-id sleeper-10-dynasty-2026 --season 2026 --draft-style sleeper_dynasty --simulate

# Persist an interactive Sleeper dynasty session:
python scripts/create_draft_strategy.py --league-id sleeper-10-dynasty-2026 --season 2026 --draft-style sleeper_dynasty --name "WR Anchor, Superflex Early QB" --strategy-json '<json>' --questionnaire-json '<json>'
```
