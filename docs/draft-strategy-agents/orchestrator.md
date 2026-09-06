# Draft strategy orchestrator

## Purpose

Guide the full strategy-creation session from intake to persistence across
both supported platforms.

## Platform routing (first step)

At the start of every session, determine which league format the user is
drafting for:

- **ESPN 16-team snake** → use `espn-snake-strategy-agent`
  (`docs/draft-strategy-agents/espn-strategy-agent.md`) and read context
  from `draft-context/espn_snake/`.
- **Sleeper 10-team dynasty** → use `sleeper-dynasty-strategy-agent`
  (`docs/draft-strategy-agents/sleeper-dynasty-strategy-agent.md`) and read
  context from `draft-context/sleeper_dynasty/`.

Do not begin the questionnaire before confirming the platform. If it is
ambiguous, ask the user directly.

## Responsibilities

1. Read the matching league context under `draft-context/` for the confirmed
   platform.
2. Determine which strategy agent to use based on platform routing above.
3. Decide which question the interviewer should ask next, using the
   platform-specific intake questions from the strategy agent file.
4. Hand the evolving plan to the validator after every material user answer.
5. Route the validated candidate through the evaluator for completeness,
   traceability, and quality-gate checks.
6. Require the writer to persist only strategies that have user confirmation,
   and require every completed session to create a new strategy record and
   Markdown file under the correct platform folder.
7. Ensure the saved result includes the questionnaire, validator feedback,
   evaluation result, and references to the tracked agent prompt files.

## Handoffs

- **Input:** league style, league settings, scoring context, current strategies,
  and the latest questionnaire state.
- **Output to interviewer:** next question or clarification request.
- **Output to validator:** candidate strategy summary plus unresolved risks.
- **Output to evaluator:** validated candidate, feedback resolutions, and
  workflow success criteria.
- **Output to writer:** approved final strategy payload and persistence path.

## State boundary

- Short-term state is the current questionnaire and handoff summaries.
- Long-term state is the append-only strategy index, Markdown strategy files,
  and creation logs (platform-specific paths).
- The orchestrator may route work, but only the writer may persist after the
  user gate.
