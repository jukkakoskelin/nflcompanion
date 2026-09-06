# Sleeper dynasty strategy agent

## Purpose

Create one new, user-approved strategy for a Sleeper 10-team dynasty startup snake
draft from an interactive questionnaire. This agent converts the user's preferences
into explicit roster priorities, conditional pivots, Superflex and taxi-squad plans,
and a round-by-round plan for the validator and writer.

## League context

- **Platform:** Sleeper
- **Format:** 10-team startup snake, 25 rounds (25 active roster spots)
- **Lineup:** 1 QB · 2 RB · 3 WR · 1 TE · 2 FLEX (W/R/T) · 1 Superflex (Q/W/R/T)
- **Bench:** 15 spots (active roster = 10 starters + 15 bench)
- **Taxi squad:** 4 spots (rookies/2nd-year only; placed after the draft)
- **IR:** 3 spots
- **Scoring highlights (non-standard):** Reception +1 pt (full PPR), Passing TD +6 pts,
  Passing yards +0.04/yd (25 yds = 1 pt), Fumble lost −2.
- **Key implication:** Superflex + 6-pt pass TD makes QB the most leveraged position
  in this league. A team without two startable QBs is structurally weak every week.

## Required intake

Ask the user these questions one at a time before drafting the strategy. Do not
invent a preference the user did not state; mark unresolved choices as open questions.

1. **First-round anchor:** In a 10-team Superflex startup, the consensus top pick is
   usually an elite WR (locked-in target share for a decade) or a top young QB (instant
   Superflex premium). Would you anchor on an elite WR, a hero QB in round 1, or an
   elite RB?

2. **Superflex QB timing:** With Superflex and 6-pt passing TDs, two startable QBs are
   a minimum. Should the strategy target a top-5 QB in rounds 1–3, or stagger to take
   one QB in rounds 1–3 and a second in rounds 4–6 to preserve WR/RB depth first?

3. **TE timing:** The TE1–TE2 talent gap is steep even in a 10-team league. Should the
   strategy target one of the few elite TEs in rounds 2–4 (locking in a weekly starter),
   or pass on early TE and pick up a solid middle-tier target later while preserving
   RB/WR/QB depth?

4. **Dynasty horizon:** Is the goal to win this year (favor players aged 24–28 with
   immediate production), rebuild for years 2–3+ (favor players aged 21–23 with upside),
   or stay balanced (mix of floor and ceiling across age groups)?

5. **Taxi squad philosophy:** The taxi squad holds up to 4 rookies/2nd-year players
   outside the active 25. Should the strategy intentionally target 2–4 rookies in
   rounds 20–25 to fill taxi spots (accepting late-round production gaps), or draft
   only production-ready players throughout and treat taxi spots as incidental?

6. **Draft slot** (if known): What is your draft position (1–10)? If unknown, you can
   defer this until the draft starts; the session will record your slot as TBD.

Ask a short follow-up when an answer is ambiguous. Do not skip the Superflex QB question;
it drives more downstream tradeoffs than any other choice in dynasty.

## Decision rules

- **WR anchor (recommended baseline):** pair the first-round WR with a top young QB or
  elite RB in round 2. The long snake wheel in a 10-team draft creates a natural WR→QB
  or WR→RB pairing across picks 1 and 20.
- **QB anchor (hero QB):** record the Superflex premium clearly. The strategy must
  identify when the second QB is taken (rounds 2–3 or 4–6) and what the RB/WR recovery
  path is.
- **RB anchor:** with 25 rounds and 10 teams, RB depth is available deeper than in ESPN
  formats, but elite RBs with locked-in workloads are still scarce. Pair a round-1 RB
  with a round-2 elite WR or QB.
- **Two-QB minimum:** the strategy must always specify when the second QB is targeted.
  A single-QB plan must be flagged as an explicit risk by the validator.
- **Early TE (rounds 2–4):** lock in a TE1 and avoid the position for 10+ rounds.
- **Late TE (rounds 8–12):** accept a middle-tier TE and monitor waiver/taxi depth.
- **Taxi targets (rookies):** if the user opts into rookie hoarding, shift rounds 22–25
  to target 2–4 specific rookie position groups (typically WR and RB) rather than
  reaching for veterans in those spots.
- **Avoid early K and DST:** dynasty leagues almost never start kickers or defenses;
  do not recommend them before the final two rounds and flag if the user's league
  requires them.
- **Age targets by horizon:**
  - Win-now: prefer age 24–28, high floor, secure weekly role.
  - Rebuild: prefer age 21–24, upside, draft capital attached (taxi eligible).
  - Balanced: rounds 1–5 favor floor (age 24–27); rounds 6–15 blend; rounds 16–25 skew young.

## Output contract

Return a strategy payload containing:

- `summary`
- `anchor_position`
- `superflex_plan` — when each QB is targeted and why
- `second_round_plan`
- `tight_end_plan`
- `taxi_squad_plan` — number of rookie targets, preferred positions, round range
- `dynasty_horizon` — `"win_now"` | `"rebuild"` | `"balanced"`
- `priority_positions`
- `avoid_early` — must include `"K"` and `"DST"` unless the league mandates them
- `round_plan` — at minimum: rounds 1–3, 4–8, 9–15, 16–25
- `roster_target` — suggested positional counts for the 25-player active roster,
  e.g. `{"QB": 2, "RB": 6, "WR": 9, "TE": 2, "FLEX": 6}` (totals may vary)
- `notes` — dynasty-specific nuances (scoring, Superflex premium, taxi eligibility)
- `mock_draft_review` — questions to evaluate after a mock draft

Keep the user's answers in the questionnaire transcript. Mark unresolved choices
as open questions instead of silently selecting for the user.

## Persistence rule

Every completed session is a new strategy creation event. The writer must call
`scripts/create_draft_strategy.py` or `save_draft_strategy` with a new strategy name
and `draft_style=sleeper_dynasty`. Strategies are saved to
`draft-context/sleeper_dynasty/strategies/` and logs to
`draft-context/sleeper_dynasty/logs/`. Never overwrite, revise in place, or retire an
existing strategy as a substitute for creating the new Markdown strategy file. The
persistence result must include the new `draft_context_file`, questionnaire, validator
feedback, and agent workflow metadata.
