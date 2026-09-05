# Draft strategy evaluator

## Purpose

Evaluate the candidate strategy after domain validation and before persistence.
The evaluator is independent of the validator: the validator finds football
and league risks, while the evaluator checks whether the workflow produced a
complete, explainable, traceable result.

## Inputs

- Questionnaire transcript and unresolved answers
- Candidate strategy payload
- Validator feedback and resolution status
- ESPN league context and current strategy index

## Quality gates

1. The strategy identifies the first-round anchor and second-round complement.
2. It handles the no-RB-in-first-two-rounds contingency explicitly.
3. It contains a QB timing rule and an elite-versus-middle-tier TE rule.
4. It includes priority positions, early fades, a round plan, and the 14-player
   roster target.
5. Every material decision is traceable to a user answer or a stated league
   constraint.
6. Validator warnings are either resolved in the strategy or surfaced for user
   confirmation.

## Output

Return:

- `passed`: whether the candidate may proceed to the user gate
- `score`: a 0-100 completeness and traceability score
- `unresolved_questions`: decisions that remain open
- `quality_feedback`: concise actionable findings
- `success_criteria`: the checks performed

Do not edit state and do not persist a strategy. The writer owns persistence
after the orchestrator receives explicit user confirmation.