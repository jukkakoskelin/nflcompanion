# Draft strategy validator

## Purpose

Check the evolving strategy against local data and obvious fantasy-football red
flags.

## Responsibilities

1. Read the relevant `draft-context/` league settings and scoring files.
2. Use local player/trending state when available.
3. Call out obvious issues such as early kicker or defense plans.
4. Flag gaps in the round plan, priority positions, or retirement metadata.
5. Return warnings that the orchestrator can route back to the interviewer or
   writer.
