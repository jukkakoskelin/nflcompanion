---
name: draft-companion
description: Use this skill during an active fantasy draft or mock draft to evaluate candidates, record confirmed picks, record opponent picks, and preview upcoming picks via native MCP calls within a 15-second budget.
---

# Live Draft Companion Workflow

This skill guides the agent during a live fantasy football draft or mock draft, ensuring strict adherence to the two-speed draft runtime architecture: fast-lane candidate recommendations and slow-lane next-pick preparation.

## Operating Principles

1. **MCP-First Runtime (No Shell Scripts)**:
   - **All draft-state operations must execute through native MCP tool calls.**
   - Do NOT run shell commands (`python scripts/draft_companion.py ...`) or invoke terminal executions during active draft or mock draft sessions.
   - Native MCP execution avoids subprocess launch latency and eliminates interactive terminal approval prompts.

2. **Fast-Lane Response Budget**:
   - Return candidate recommendations within **15 seconds** (targeting <5 seconds).
   - Scoring runs deterministically from local snapshots (`state/players/` and `state/players/trending/`).
   - Do NOT execute network refreshes or broad web searches during the fast-lane decision window.

3. **Deterministic Candidate Scoring**:
   - Candidate ranking is computed by deterministic Python code via the `draft_recommend_candidates` MCP tool.
   - Synthesize the scorecard: provide one concise sentence of guidance per candidate and highlight factor trade-offs.
   - Never invent player stats, projections, or ranking certainty.

4. **Zero-Delay Pick Recording (User Instruction Gate)**:
   - When the user explicitly states their selection (e.g., *"Picked Nacua"*, *"Pick Lamb"*, *"Taking Hurts"*), **record it immediately** via `draft_record_pick` with `confirmed: true`.
   - Do NOT ask an extra conversational confirmation question (*"Are you sure?"* or *"Please confirm"*); the user's pick statement is the confirmation.
   - NEVER record a pick automatically merely because it was recommended without user instruction.

---

## MCP Tool Reference for Draft Sessions

### 1. Inspect or Resume Draft Session (`draft_get_session`)
Check current draft state, current pick number, roster composition, position counts, and remaining needs:
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026
}
```
Use this when starting or resuming a session to inspect current team needs before candidates are entered.

### 2. Initialize Draft Session (`draft_init_session`)
Start a new draft session (or return existing with `allow_existing: true`):
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026,
  "draft_style": "espn_snake",
  "team_count": 16,
  "user_slot": 9,
  "reverse_round": true,
  "allow_existing": true
}
```

### 3. Candidate Recommendation - Fast Lane (`draft_recommend_candidates`)
Evaluate 2 to 4 candidate player names or surnames against the active strategy, roster needs, and trending activity:
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026,
  "candidates": ["Barkley", "Jefferson", "St. Brown"]
}
```
*Notes*:
- Deterministically filters out already-drafted players (both user selections and observed opponent picks).
- Returns candidate factor scores, rankings, rationales, and the current user roster summary.

### 4. Record Confirmed User Pick (`draft_record_pick`)
Prompt the user to confirm their selection. Only call this tool once the user has explicitly confirmed:
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026,
  "provider_id": "4034",
  "full_name": "Saquon Barkley",
  "confirmed": true
}
```
*Rules*:
- `confirmed` must be `true`. If `false` or missing, the tool returns a permission error.
- If `position` or `team` are omitted, the tool automatically resolves them from the local player snapshot.

### 5. Record Opponent Pick (`draft_record_observed_pick` / `draft_observe_pick`)
When observing selections made by other teams in the league:
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026,
  "overall_pick": 10,
  "full_name": "Justin Jefferson"
}
```
*Notes*:
- Advances the overall draft sequence (`current_overall_pick`).
- Removes the player from upcoming recommendations and watch lists.
- Auto-resolves `provider_id`, `position`, and `team` from the player snapshot when `full_name` is provided.

### 6. Next-Pick Preview - Slow Lane (`draft_next_pick_preview`)
Generate upcoming target positions, tiered watch lists, and availability estimates for the user's next turn:
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026
}
```

### 7. Mid-Draft Strategy Adjustments (`draft_update_strategy`)
Update tactical priority positions, avoid lists, or strategy notes mid-draft without altering the immutable baseline strategy:
```json
{
  "league_id": "espn-16-2026-slot-9-3rr",
  "season": 2026,
  "priority_positions": ["WR", "TE"],
  "notes": "Target elite TE before round 7 positional run"
}
```

---

## Manual CLI Fallback (Human/Terminal Debugging Only)

For manual offline testing or human CLI operations outside agent sessions:
```powershell
python scripts/draft_companion.py init --league-id espn-16-2026-slot-9-3rr --season 2026 --draft-style espn_snake --team-count 16 --user-slot 9 --reverse-round
python scripts/draft_companion.py recommend --league-id espn-16-2026-slot-9-3rr --season 2026 "Barkley" "Jefferson" "St. Brown"
python scripts/draft_companion.py record-pick --league-id espn-16-2026-slot-9-3rr --season 2026 --provider-id 4034 --full-name "Saquon Barkley" --position RB --team PHI --overall-pick 9 --confirmed
python scripts/draft_companion.py observe-pick --league-id espn-16-2026-slot-9-3rr --season 2026 --provider-id 4035 --full-name "Justin Jefferson" --position WR --team MIN --overall-pick 10
python scripts/draft_companion.py next-pick --league-id espn-16-2026-slot-9-3rr --season 2026
```
