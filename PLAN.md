# NFL Fantasy Draft Companion Plan

Status: in progress - Sleeper Dynasty strategy support added; strategy creation skill,
agent prompts, and validation now dual-platform (ESPN + Sleeper); draft companion
roster needs and TBD slot extended for dynasty; 85 tests passing.
Priority: draft-ready for the Sleeper dynasty startup mock and live drafts

## Product goal

Provide a fast, explainable draft companion that keeps the user's draft state in
Markdown, lets Copilot help create and revise strategies, and provides a canvas
view at each pick:

1. The user enters two or three available players.
2. The app ranks them against the active strategy, roster, player data, and
   imported cheat sheets.
3. It gives one sentence of guidance per candidate.
4. The user records the selection.
5. The app explains what to watch for before the next turn, based on the
   strategy and selections so far.

The app must still be useful if an external site or API is unavailable during
the draft. Imported snapshots and explicit user decisions are therefore
first-class data, not a cache that can be silently replaced.

## Scope and delivery order

### Milestone 0: draft-ready foundation (do first)

- Define a small, provider-neutral player schema.
- Add adapters for importing a Sleeper snapshot and an ESPN snapshot where
  practical. Sleeper has documented public read endpoints; ESPN data access is
  less stable and may require a user-provided export or manually uploaded file.
- Support CSV/JSON and pasted or uploaded cheat sheets. Preserve the original
  file and record source, date, format, and parsing warnings.
- Store leagues, strategies, rosters, imported data, and draft events as
  human-readable Markdown state files.
- Add a deterministic candidate scoring function with visible factor scores.
- Build a canvas showing current pick, roster, strategy, top needs, candidate
  ranking, rationale, and next-watch list.
- Record each pick as an append-only draft event and update the roster.

### Milestone 1: Copilot-assisted workflow

- Add repository instructions describing the state-file contract and safe
  update rules.
- Add a custom draft analyst agent that reads only the relevant state files,
  proposes structured recommendations, and never records a pick without
  explicit user confirmation.
- Add prompts/commands for creating two alternate strategies, comparing them,
  switching the active strategy, and reviewing a completed pick.
- Add evaluation fixtures with known rosters, cheat sheets, and candidate
  situations so recommendations can be regression-tested.

### Milestone 2: provider and UX hardening

- Improve player identity reconciliation across Sleeper, ESPN, and cheat sheets.
- Add optional refresh commands with timestamps, source precedence, and
  stale-data warnings.
- Add import validation, duplicate detection, backups, and an undo/reversal
  event for an accidental selection.
- Consider a persistent web/Tauri UI only after the Markdown/canvas workflow is
  proven during a real draft.

## Post-mock findings and follow-up

The ESPN 16-team, slot-9, third-round-reversal mock received an ESPN draft
grade of `C`. The roster's relative strength was bench depth; its main
weaknesses were tight end and defense. The mock used a 30-second decision
window and advanced much faster than a real draft, so response latency is a
draft-readiness requirement rather than a cosmetic UX concern.

### First mock enhancement priorities

The first mock also exposed gaps in the recommendation path itself. The saved
recommendations repeatedly tied candidates at `75` or `85`, assigned `high`
confidence without enough differentiating evidence, surfaced unresolved names
alongside ranked candidates, and failed to resolve common display labels such
as `Packers DEF`. The next implementation work should therefore be ordered as
follows:

1. **P0: make recommendations discriminating and trustworthy.** Add tier or
  ranking evidence, roster-state penalties, positional scarcity, and injury or
  availability risk to the scorecard. Confidence must be derived from match
  quality and evidence completeness; unresolved or ambiguous inputs must stop
  ranking for that candidate rather than appear as a normal recommendation.
2. **P0: enforce endgame roster coverage.** Add a remaining-picks checkpoint
  that distinguishes starter quality from merely filling a position. It must
  flag a weak TE or DEF tier, protect the required minimum roster, and compare
  the replacement value of a late specialist with an RB/WR upside pick.
3. **P1: harden fantasy identity resolution.** Normalize provider and display
  aliases (`DEF`/`D/ST`, team name plus position, punctuation, and common
  abbreviations), retain the original input, and return a short clarification
  choice when multiple players remain. Add fixtures for `St. Brown`, `Brooks`,
  and `Packers DEF`.
4. **P1: make the fast lane usable under draft pressure.** Measure each
  recommendation from submission through first actionable output, keep the
  session context warm, and return a bounded provisional answer before deeper
  evidence or refresh work. Test against a 30-second decision window as well
  as the existing 15-second hard budget.
5. **P1: close the mock feedback loop.** Persist the mock grade, roster-quality
  notes, recommendation record, and post-draft review as linked artifacts so a
  later strategy revision can tell whether a weakness came from strategy,
  player valuation, identity matching, or unavailable data.

### Second mock findings and follow-up (2026-09-05)

The second ESPN 16-team 3RR mock draft (session `espn-16-2026-mock-2`) received an
ESPN draft grade of `C`. Bench depth was scored as a strength, but QB was a
noted weakness, and three of the top five selections shared the same NFL bye
week. Additionally, interactive command execution prompted repeatedly for user
approval, hindering the fast-lane draft experience.

The following priorities are added to the refactoring roadmap:

1. **P0: Pre-draft bye-week analysis and conflict avoidance.**
   - Import and persist NFL team 2026 bye weeks in player snapshot metadata.
   - Run a pre-draft bye week distribution analysis at draft-session start so the
     user is alerted to key bye week concentrations before round 1 begins.
   - Introduce a bye-week penalty to `recommend_candidates` when a candidate
     shares a bye week with existing core starters at the same or flex position.
   - Surface bye-week tags in candidate scorecards and next-pick previews.

2. **P0: Safe script pre-approval and frictionless agent-state interaction.**
   - Enable safe, pre-approved execution of draft companion commands by
     configuring Antigravity command allowlists / permission grants for
     `python scripts/draft_companion.py*`.
   - Promote direct MCP server integration (`src/nflcompanion/mcp_server.py`) as
     the preferred runtime path for `draft_recommend_candidates`,
     `draft_next_pick_preview`, and `draft_record_pick`, avoiding raw shell
     execution overhead and confirmation prompts.
   - Maintain strict safety boundaries: read-only evaluation and recommendations
     execute seamlessly without approval prompts, while pick commits continue
     to enforce an explicit human confirmation gate (`confirmed: true`).

Acceptance checks for the next slice: materially different candidates no
longer receive identical scores without an evidence-based tie; `high`
confidence is impossible for unresolved or stale inputs; `Packers DEF` resolves
to the canonical provider record; a late roster review identifies TE/DEF
quality risk separately from positional count; bye-week conflicts are flagged
before selection; and the first actionable result is measured in a local,
offline fixture.

### Third mock findings and follow-up (2026-09-05)

The third ESPN 16-team 3RR mock draft (session `espn-16-2026-mock-3`) executed
the RB Anchor, WR Complement, Value Round 3 blueprint, but again received an
ESPN draft grade of `C`. Key insights and friction points:

1. **Information Density & Cognitive Overload**:
   - In a fast 30-second live draft window, verbose Markdown tables and lengthy
     factor breakdowns create too much cognitive burden.
   - The user needs immediate, high-salience visual hierarchy:
     - **Primary Round Focus**: Prominently emphasize the exact target position
       (e.g., `TARGET: WR1`) at each round.
     - **Top 1-2 Recommended Picks**: Surface only the top 1-2 candidates with
       bold, glanceable tags (bye week, role, rank).
     - **Secondary Deeper Details**: Place detailed factor math and multi-player
       fallbacks into lower-emphasis or expandable sections so they do not
       distract unless the user has spare time to review them.

2. **Runtime Execution Verification (MCP vs. Python Scripts)**:
   - Python scripts (`scripts/draft_companion.py`) were executed rather than
     native MCP tools (`draft_recommend_candidates`, `draft_record_pick`, etc.)
     because the `nflcompanion` MCP server was not registered in the active
     Antigravity host toolset for the session.
   - For frictionless draft execution without command prompts, verify
     Antigravity MCP server discovery (`~/.gemini/config/mcp_config.json` and
     `.agents/mcp_config.json`) so native MCP tools are injected at session start.

3. **Roadmap Addition: Local Draft UI (Web / Canvas Dashboard)**:
   - Live drafting demands a dedicated, visual canvas rather than relying solely
     on conversational chat scrolling.
   - Plan a lightweight local web dashboard (`http://localhost:...` or Canvas UI)
     that displays:
     - Prominent round/pick counter and target position banner.
     - Visual draft board with glanceable roster needs and bye-week flags.
     - Live candidate cards (top 1-2 highlighted) with instant one-click or
       agent-synced selection confirmation.
   - Detailed technical design to be planned in the upcoming milestone before
     implementation.

### Draft response-time optimization

- Measure recommendation latency from candidate submission to the first
  actionable answer, including state reads and player/trending lookups.
- Keep the active session context, current roster, position counts, injury
  flags, strategy, and latest trend snapshot ready for reuse instead of
  rebuilding them for every pick.
- Return a short provisional recommendation immediately, then attach evidence
  and deeper comparison details without blocking the decision window.
- Define a draft-mode response budget and test it with representative 16-team
  ESPN candidate sets; surface stale or unavailable data instead of waiting
  indefinitely for a refresh.
- Add a post-mock latency review so response-time regressions are visible along
  with recommendation-quality regressions.

### Roster summaries and pick records

- Every recommendation response and post-pick summary must list all players
  selected by the user, grouped or labeled by position, including current
  position counts and remaining roster needs.
- Include the selected player's position in every human-readable pick
  confirmation, event record, and canvas view; normalize `DEF`/`DST` to the
  league's display label without losing the provider value.
- Add tests that verify roster summaries remain correct after user picks and
  observed opponent picks, including the ESPN 14-player target.

### Injury and availability context

- Preserve and normalize Sleeper fields such as `injury_status`,
  `injury_body_part`, `injury_notes`, and practice/injury metadata when
  importing the player snapshot.
- Show a concise availability warning beside each candidate and in the
  watchlist when a player is questionable, out, injured, or otherwise carries
  a non-clear status; do not silently treat missing status as healthy.
- Include injury status in deterministic candidate scoring as a visible risk
  factor, with the strategy and user able to override the default weighting.
- Add fixtures and tests for healthy, questionable, out, missing-status, and
  stale injury data.

### Session-start trend capture

- Fetch the Sleeper trending add/drop snapshot at draft-session start and save
  its timestamp, lookback window, source, and raw immutable payload with the
  session provenance.
- Use that session-start snapshot as the baseline trend signal for the first
  recommendation, then allow an explicit refresh that creates a new dated
  snapshot rather than overwriting the baseline.
- Include trend direction and count in candidate evidence and use it as a
  tiebreaker after roster need, player value, availability, and strategy fit;
  trends must not override obvious injury or role risk without showing the
  tradeoff.
- Define an offline/fetch-failure path that keeps the draft usable, labels the
  trend data stale or unavailable, and reduces confidence instead of
  fabricating a trend signal.
- Add tests proving that session initialization records the trend snapshot and
  that recommendations use the captured add/drop data consistently.

## Data-fetch and data-management plan (first implementation)

### Canonical entities

- `Player`: stable internal id, provider ids, name, position, team, status,
  age/season metadata when available, and source provenance.
- `League`: platform, league id, format, scoring settings, roster slots,
  draft type/order, and current pick.
- `Ranking`: player id, rank, tier, projection/value fields, source, timestamp,
  and optional position/scoring context.
- `CheatSheet`: source name, URL or filename, retrieved/imported timestamp,
  column mapping, raw-file reference, and normalized rows.
- `Roster`: league, team, owner, selected player ids, open slots, and needs.
- `DraftEvent`: pick number, round, overall pick, team, player, timestamp,
  source (`user`/`import`), and notes.
- `Strategy`: name, league scope, priorities, fades, tier/risk rules, and a
  short explanation of when it should be preferred.

### Markdown state layout

```text
state/
  leagues/<league-id>.md
  strategies/<strategy-id>.md
  rosters/<league-id>/<team-id>.md
  drafts/<league-id>/events.md
  players/snapshot-<source>-<date>.md
  rankings/<source>-<date>.md
  cheatsheets/<sheet-id>.md
  imports/raw/<original-file>
```

Markdown is the source of truth for user-editable decisions and draft history.
Machine-readable tables/front matter should be used inside the files so both
Copilot and code can parse them. Raw imports are immutable; normalized snapshots
are new files rather than in-place edits.

### Provider strategy

1. **Sleeper first:** implement a read-only adapter around the public API and
   save a dated snapshot. Do not depend on it being reachable during the draft.
2. **ESPN second:** prefer an official export or uploaded JSON/CSV where
   available. Treat direct ESPN endpoints as an experimental adapter because
   they are not a stable public contract and may require league/user context.
3. **Cheat sheets:** accept CSV, JSON, Markdown, HTML, and pasted tables through
   an import command. Require a review when columns or player identities are
   ambiguous.
4. **Identity matching:** match exact provider ids first, then normalized name
   plus team/position; never silently merge uncertain matches. Store unmatched
   rows and ask for resolution.
5. **Freshness:** every recommendation displays source timestamps and an
   explicit stale/offline warning. Missing data should reduce confidence, not
   produce fabricated values.

### Recommendation algorithm

Use deterministic filtering and scoring before asking Copilot to explain:

- remove drafted, roster-ineligible, suspended, or duplicate candidates;
- score positional need, strategy fit, tier/value, projected production,
  scarcity, risk, and cheat-sheet consensus;
- apply league settings and dynasty/keeper horizon;
- return factor scores, source references, confidence, and a one-sentence
  explanation for each candidate;
- produce a next-watch list (positions, tiers, and specific players) rather than
  pretending to know future picks.

Copilot should synthesize and explain these results, not invent rankings or
mutate state. A user confirmation is required before appending a selection.

## Code versus Copilot responsibilities

### Deterministic application code

- Provider clients and import parsers.
- Schema validation, normalization, identity matching, and provenance.
- Markdown read/write, append-only draft events, backups, and conflict checks.
- League scoring rules, roster eligibility, snake-pick math, and candidate
  scoring.
- Canvas data model and rendering.
- Tests and fixtures for all of the above.

### Strategy creation agents

- Use the orchestrated multi-agent workflow plus the ESPN strategy agent prompt
  to interview for first-round anchor, second-round complement, QB timing, and
  TE timing.
- Keep domain validation separate from workflow evaluation: validator agents
  check football risks, while evaluator agents check completeness, evidence,
  and success criteria before the writer runs.
- Every completed interactive ESPN strategy session creates a new strategy
  record, Markdown file, and append-only creation-log entry; existing
  strategies are never overwritten.

### Copilot custom agent/instructions

- Interview the user to create at least two materially different strategies.
- Explain tradeoffs and compare recommendations to the active strategy.
- Ask for clarification on ambiguous imports or identity matches.
- Summarize the deterministic score into concise draft guidance.
- Produce next-watch guidance from current state.
- Keep decisions inspectable by citing state files and source rows.

### Human-in-the-loop boundaries

- User approves strategy activation and every recorded pick.
- User resolves uncertain player matches and conflicting cheat-sheet columns.
- No external account writes, league transactions, or irreversible actions in
  the MVP.

## Canvas design

The draft canvas should fit one decision on screen:

- league/platform and pick number;
- active strategy plus a switch-strategy control;
- roster slots, filled positions, and remaining needs;
- 2–3 candidate input rows;
- ordered recommendation with one-sentence guidance and confidence;
- expandable evidence (scores, cheat-sheet rows, source timestamps);
- “record selection” confirmation;
- next-watch positions/tiers/players.

## GH-600 design considerations applied here

The current Microsoft Learn study guide weights tool use (20–25%), evaluation
(15–20%), orchestration (15–20%), architecture/SDLC (15–20%), memory/state
(10–15%), and guardrails (10–15%). This project is intentionally a practical
study exercise:

- **Architecture/SDLC:** separate plan, deterministic execution, and approved
  state mutation; define inputs, outputs, and success criteria.
- **Tools/MCP:** use least-privilege, read-only data tools first; make tool
  permissions and provider failures visible.
- **Memory/state:** Markdown snapshots and append-only events provide durable,
  portable state and reduce context drift.
- **Evaluation:** fixtures measure identity-match accuracy, ranking stability,
  citation/provenance coverage, and whether a pick requires confirmation.
- **Orchestration:** keep ingestion, scoring, analyst explanation, and state
  mutation as separable components with inspectable handoffs.
- **Guardrails:** no silent merges, no fabricated player data, no unconfirmed
  picks, and no external writes in the first release.

## Agentic guardrails

To keep implementation changes tied to an inspectable plan, this repository
uses the following lightweight guardrails:

- `PLAN.md` remains the required planning artefact for implementation changes.
- GitHub Actions verifies that changes under `src/`,
  `scripts/fetch_sleeper_players.py`, `scripts/query_players.py`, or
  `pyproject.toml` are accompanied by a `PLAN.md` update.
- GitHub Actions runs the existing `unittest` suite so implementation changes
  are verified against tests in pull requests and on `main`.

## MCP and app configuration

Configure only what is needed:

1. **GitHub MCP server (recommended):** repository/files, issues, and pull
   requests for versioned state, code review, and traceable changes. Prefer
   read-only tools during the draft.
2. **Fetch/browser MCP server (optional):** retrieving public Sleeper
   documentation or a provider snapshot when the user explicitly requests a
   refresh. Keep it out of the critical draft path.
3. **Filesystem/workspace tools (recommended):** the local agent already needs
   scoped access to this repository to read/write `state/` and imports. Restrict
   writes to the repository and require confirmation for state mutation.
4. **No fantasy-platform write MCP server for MVP:** do not configure tools that
   can modify Sleeper or ESPN leagues until authentication, authorization,
   audit logging, and rollback are designed.

The exact MCP names depend on the Copilot host and its registry. Use an allow
list containing only the selected read tools and the explicitly approved
state-writing tool. Do not add a generic internet or shell MCP server when a
scoped fetch or repository tool is sufficient.

### Integration smoke-test status (2026-09-05)

- **GitHub MCP:** working. A read-only fetch of `README.md` from
  `jukkakoskelin/nflcompanion` on `main` succeeded.
- **Filesystem MCP:** server is reachable, but the configured allow-list contains
  only `D:\repos\nflcompanion`. It rejects this worktree at
  `C:\Users\jukka\.copilot\repos\copilot-worktrees\nflcompanion\...`. Add the
  active workspace path (or configure the MCP host to provision the correct
  worktree path) before relying on filesystem operations.
- **Fetch:** the official reference server is
  `modelcontextprotocol/servers/src/fetch`, runnable with `uvx
  mcp-server-fetch`. Keep its default `robots.txt` behavior, restrict outbound
  access if the host supports URL policy, and do not enable
  `--ignore-robots-txt` for this project. The server can reach internal IP
  addresses, so it must not be exposed to untrusted prompts without network
  egress controls.

## Study references

- [GH-600 study guide](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/gh-600)
- [Develop AI agents on Azure learning path](https://learn.microsoft.com/en-us/training/paths/develop-ai-agents-azure/)
- [Integrate MCP Tools with Azure AI Agents](https://learn.microsoft.com/en-us/training/modules/connect-agent-to-mcp-tools/)
- [Build agent-driven workflows using Microsoft Foundry](https://learn.microsoft.com/en-us/training/modules/build-agent-workflows-microsoft-foundry/)

The study guide page currently states that a score of 700 or greater is
required to pass. Microsoft Learn content and exam objectives can change, so
re-check the linked pages before exam preparation.

## Data-layer implementation started

The initial vertical slice is implemented in this repository:

- `scripts/fetch_sleeper_players.py` fetches the public Sleeper endpoint and
  writes an immutable, dated raw JSON snapshot plus a Markdown provenance
  manifest using atomic file replacement.
- `src/nflcompanion/state_store.py` provides a provider-neutral read/query
  contract for snapshot data.
- `scripts/query_players.py` is the temporary canvas-facing JSON interface for
  querying the latest local state snapshot.
- `state/README.md` documents the durable state boundary.
- `tests/test_state_store.py` covers normalization and filtering.
- `.github/extensions/sleeper-player-data/extension.mjs` provides agent tools
  that ensure/query local state and a canvas for testing those queries.

The fetch MCP is intentionally an agent/environment tool, not a hidden
dependency inside application code. Copilot can use it to retrieve public
content and save an approved snapshot; the local adapter also supports direct
read-only retrieval for repeatable CLI operation and offline use. This split
keeps provider access observable and lets the draft continue from stored state.

The project extension follows the same boundary: it checks the repository's
ignored `state/players/` snapshots first, fetches only when absent or explicitly
refreshed, and returns the snapshot update timestamp with every query.

### Trending player context at session start

Sleeper's `/players/nfl/trending/<add|drop>` endpoint (see
https://docs.sleeper.com/#trending-players) reports rostership add/drop
activity that changes constantly, which is directly useful when building or
revising a draft strategy. This is now wired in as durable, local-only state:

- `scripts/fetch_sleeper_trending.py` fetches both the `add` and `drop`
  trending lists and writes an immutable, dated raw JSON snapshot plus a
  Markdown provenance manifest under `state/players/trending/`, using the same
  atomic-write approach as the player snapshot fetcher.
- `src/nflcompanion/state_store.py` gained `latest_trending_snapshot`,
  `load_trending`, and `query_trending_players`, which enrich raw
  `player_id`/`count` entries with names/positions/teams from the latest
  player snapshot when one is available.
- `scripts/query_trending_players.py` is the CLI/canvas-facing query
  interface, mirroring `scripts/query_players.py`.
- `.github/extensions/sleeper-player-data/extension.mjs` now registers an
  `onSessionStart` hook that fetches a fresh trending snapshot every time an
  agent session starts or resumes (falling back to the last cached snapshot if
  the fetch fails) and injects a short summary of the top trending adds/drops
  as hidden context. It also adds a `sleeper_query_trending_players` tool and
  a matching canvas action so both human and agentic users can query the
  local snapshot directly.
- Like player snapshots, trending snapshots and manifests are ignored by git
  (`state/players/trending/raw/*.json`, `state/players/trending/sleeper-trending-*.md`)
  because they are provider data that should be fetched locally, not versioned.

## Actual draft companion runtime plan

The draft runtime is a human-controlled, two-speed workflow. Deterministic
application code owns draft math, identity matching, filtering, scoring, and
state writes. Agents explain the result and prepare context; they must not
invent rankings or record a pick without explicit confirmation.

### Draft session state

Create one durable session per league and season under
`state/drafts/<league-id>/`:

- `session.md`: league settings, draft order, team/pick position, 90-second
  decision-window setting, active strategy, lifecycle (`planned`, `active`, or
  `completed`), and source freshness.
- `events.md`: append-only events for user-confirmed picks, observed opponent
  picks, candidate submissions, recommendation results, and corrections.
- `living-strategy.md`: the mutable working strategy for this draft, including
  selected players, roster slots remaining, strategy adjustments, next-round
  targets, availability estimates, and unresolved questions.
- `recommendations/`: immutable JSON/Markdown recommendation records linked to
  the event that produced them.

The existing saved strategy remains an immutable baseline. The living strategy
is a session view derived from that baseline plus confirmed draft events; it is
saved as the final session strategy only when the user ends the draft. A pick
submission always has an explicit confirmation step and an idempotency key so
retries cannot duplicate it.

### Two-speed agent workflow

Use an orchestrator with separate fast and slow lanes rather than putting all
agents in a serial chain during the 90-second window.

**Fast lane: candidate decision**

1. The user submits 2-4 surnames, optionally with first name, position, or
   team, plus the current pick if it is not already in session state.
2. A deterministic resolver matches each input to the local player snapshot.
   Exact provider id or unambiguous normalized name wins; ambiguous matches are
   returned immediately for clarification and are never silently ranked.
3. A stateless recommendation worker loads the living strategy, roster, draft
   position, current events, and latest local snapshots. It filters drafted or
   ineligible players and scores the candidates by need, strategy fit, tier or
   value, scarcity, production, risk, and available trend evidence.
4. The analyst agent receives only the structured scorecard and returns the
   ordered list, one short sentence per player, confidence, and source
   timestamps. The response must be bounded to the submitted candidates.
5. The user chooses whether to record a pick. The agent records nothing merely
   because it recommended a player.

Target: return the structured ranking in 5 seconds or less from local data,
with a hard response budget of 15 seconds. No network refresh, broad player
search, mock draft, or next-round forecast may block this lane.

**Slow lane: next-round preparation**

After a confirmed pick, enqueue a background preparation job. It computes the
next user pick using centralized snake-draft math, then queries player and
trending snapshots for the positions and tiers the active strategy prefers.
It returns:

- next pick number, round, and number of selections before the user picks;
- recommended positions and the reason they are priorities now;
- a watch list of specific players grouped by tier;
- an availability estimate based on draft position, observed picks, and a
  configurable ADP or ranking source, clearly labeled as an estimate;
- fallback positions and players if a positional run occurs;
- data freshness, missing-data warnings, and confidence.

This result updates `living-strategy.md` only as a generated proposal. The
user may accept or edit it, and the accepted version is recorded as an event.
The slow lane may take longer and may refresh approved read-only sources, but
it must never delay the next fast-lane decision.

### Agent roles and contracts

- **Draft orchestrator:** validates session state, routes fast or slow work,
  enforces deadlines and human gates, and exposes partial results.
- **Candidate resolver/scorer:** deterministic code, not an LLM; resolves
  surnames, removes unavailable players, calculates factor scores, and emits
  evidence IDs.
- **Fast draft analyst:** ranks only supplied candidates and writes concise
  rationale from the scorecard. It cannot call external sources or mutate
  state.
- **Roster and strategy validator:** checks roster legality, strategy drift,
  early kicker/defense red flags, and whether the recommendation conflicts with
  a confirmed user preference.
- **Next-pick forecaster:** runs in the slow lane and produces tiered watch
  lists and availability ranges, never a claim of certainty.
- **Session writer:** the only state-mutating role; appends confirmed events,
  rebuilds the living strategy, and finalizes it after the draft.

Fast-lane handoff output should be a typed object containing session id,
candidate resolutions, ordered recommendations, factor scores, one-sentence
rationales, confidence, evidence references, and an expiration timestamp.
Slow-lane output should contain the next-pick calculation, watch lists,
availability assumptions, freshness, and proposed living-strategy changes.

### Snake-draft rules

Implement and unit-test one provider-neutral function for overall pick and the
next user pick. For `N` teams, a normal snake draft gives pick `p` in round
`r = floor((p - 1) / N) + 1`; the within-round slot is forward in odd rounds
and reversed in even rounds. Keep third-round reversal as an explicit league
rule, not a hidden ESPN assumption. The session stores the exact draft order,
team count, first pick, reversal rule, and any platform-specific exception so
forecasts are reproducible.

### Delivery order and acceptance tests

1. **Implemented:** add session schema, append-only event writer,
  living-strategy projection, idempotency, and snake-pick math.
2. **Implemented:** add surname/partial-name resolution and deterministic 2-4
  candidate scoring with fixture data and ambiguity tests.
3. Add the fast analyst contract and a canvas/command that enforces the 15
   second response budget and confirmation gate.
4. **Implemented locally:** add the slow next-pick forecaster using
  player/trending snapshots, observed picks, priority ordering, and explicit
  heuristic availability labels. Tier/ADP source integration remains.
5. Add session finalization that saves the living strategy and links its event
   history to the original strategy baseline.
6. Add end-to-end fixtures for normal snake and third-round reversal drafts.

The minimum draft-ready checks are: four candidates rank deterministically;
ambiguous surnames stop for clarification; a drafted player cannot be ranked;
the same confirmed pick cannot be appended twice; the next pick is correct at
round boundaries and reversal points; fast results do not depend on network
availability; every rationale cites local evidence; and finalization preserves
the full event history and accepted living strategy.

The implemented slice lives in `src/nflcompanion/draft_companion.py` and
`scripts/draft_companion.py`. It persists sessions under
`state/drafts/<league-id>/<season>/`, keeps recommendations offline and bounded
to submitted candidates, and provides a local next-pick watch list. Tier/ADP
source integration and the Copilot analyst prompt contract remain next-slice
work.

Next:

1. Add cheat-sheet import parsing and ambiguity reports.
2. Expand the strategy slice so interviewer/validator/writer agents can persist
   draft-context Markdown strategies, retirement metadata, and append-only
   creation logs, including a reviewer-friendly Markdown log mirror, with a
   non-interactive simulation entry point for testing.
2a. Track explicit orchestrator/interviewer/validator/writer prompt contracts in
    repository Markdown and surface them in saved strategy workflow metadata so
    reviewable multi-agent orchestration is part of the durable state.
3. Add the fast analyst contract and a temporary canvas view on top of the
  deterministic candidate scoring now implemented.
4. Add an agent instruction contract that requires citations and confirmation
   before state mutation.
5. Plan a local draft UI (lightweight local web dashboard / canvas view)
   prioritizing glanceable visual hierarchy, high-contrast round target focus,
   and simplified 1-2 candidate cards for fast 30-second draft decision windows.

## Dual Copilot and Antigravity agentic support

The agentic capabilities are now dual-compatible across both GitHub Copilot and
Google Antigravity:

- Standard zero-dependency Python MCP server in `src/nflcompanion/mcp_server.py`
  and `scripts/mcp_server.py` exposing player state, query, draft session,
  recommendation, pick recording, opponent pick observing, and preview tools.
- MCP-first draft agent interaction: live draft and mock draft workflows run
  exclusively through native MCP tools (`draft_get_session`, `draft_init_session`,
  `draft_recommend_candidates`, `draft_record_pick`, `draft_record_observed_pick`,
  `draft_next_pick_preview`, `draft_update_strategy`), eliminating terminal shell
  confirmation friction and subprocess overhead while maintaining strict human
  confirmation gates (`confirmed: true`) for user pick commits.
- Dual MCP configuration in `.agents/plugins/nflcompanion/mcp_config.json`,
  `.agents/mcp_config.json`, and `.vscode/mcp.json`.
- Unified agent rules in `AGENTS.md` and `.github/copilot-instructions.md`.
- Antigravity lifecycle hooks in `.agents/hooks.json` for PreInvocation trending
  injection and Stop-time plan guardrail checks.
- Antigravity skills in `.agents/skills/draft-strategy/` and
  `.agents/skills/draft-companion/`.
- Existing GitHub Copilot extension and canvas UI in `.github/extensions/`
  remain intact and backwards-compatible.

## Sleeper Dynasty strategy support (2026-09-06)

The strategy creation workflow is now dual-platform across ESPN 16-team snake
and Sleeper 10-team dynasty startup snake. The following changes were made:

### New files

- `docs/draft-strategy-agents/sleeper-dynasty-strategy-agent.md` — new strategy
  agent prompt with 10-team Superflex startup questionnaire (6 questions: anchor,
  Superflex QB timing, TE timing, dynasty horizon, taxi-squad philosophy, draft
  slot), decision rules (age targets, two-QB minimum, taxi hoarding vs. floor),
  and output contract (`superflex_plan`, `taxi_squad_plan`, `dynasty_horizon`,
  25-player `roster_target`, etc.). Mirrors the ESPN agent but is tuned for
  dynasty/Superflex/PPR.

### Modified files

- `src/nflcompanion/state_store.py`:
  - Added `_DEFAULT_AGENT_ROLES_BY_STYLE` and `_DEFAULT_AGENT_PROMPT_FILES_BY_STYLE`
    — per-draft-style dicts so `sleeper_dynasty` routes to the dynasty strategy
    agent and ESPN routes to the ESPN agent.
  - `_agent_workflow()` now reads the draft style from `session_config` and selects
    the correct agent role/prompt file and style-specific `success_criteria`.
  - `validate_draft_strategy()` now warns when `superflex_plan` or `dynasty_horizon`
    is missing for `sleeper_dynasty`.
  - `rate_draft_strategy()` now awards bonus points for `superflex_plan` (+5),
    `taxi_squad_plan` (+3), and `dynasty_horizon` (+2) for `sleeper_dynasty`.
  - `save_draft_strategy()` defaults `collaborating_agents` to the style-specific
    role map instead of the ESPN-only defaults.
  - Both simulated `sleeper_dynasty` strategies in `_SIMULATED_STRATEGIES` have
    been updated to include `superflex_plan`, `dynasty_horizon`, and
    `taxi_squad_plan` so they pass the new validation without warnings.

- `src/nflcompanion/draft_companion.py`:
  - `calculate_roster_summary()` now accepts `draft_style` and
    `target_roster_size=None`. For `sleeper_dynasty`: default 25-slot target,
    2-QB minimum (with Superflex label), 3-WR minimum, no DEF/K required.
    For `espn_snake`: behavior unchanged (14 slots, DEF+K required).
  - `create_draft_session()` now accepts `user_slot=0` for TBD draft position.
    Session metadata records `draft_slot_status: "TBD"` until the slot is
    known; valid non-zero slots record `"confirmed"`.
  - New `confirm_draft_slot()` helper updates a TBD session with the real slot
    once it is revealed by the platform at draft start.

- `.agents/skills/draft-strategy/SKILL.md`:
  - Added "Choosing the Platform" section at the top.
  - Extended interviewer section with the Sleeper Dynasty 10-team startup snake
    intake questions (6 questions matching the strategy agent file).
  - Strategy Agent entry now shows both ESPN and Sleeper dynasty routes.
  - Writer entry now notes platform-specific save paths.
  - Added `sleeper_dynasty` CLI examples.

- `docs/draft-strategy-agents/orchestrator.md`:
  - Added "Platform routing (first step)" section instructing the orchestrator
    to ask ESPN vs. Sleeper at the top of every session and route to the correct
    strategy agent before beginning the questionnaire.

### Tests added

- `tests/test_state_store.py`: 9 new dynasty tests — saves to correct folder,
  superflex/horizon validation warnings, no-warning for complete strategy,
  rating bonus, agent workflow routing for both styles, success_criteria content,
  simulate produces valid strategy.
- `tests/test_draft_companion.py`: 12 new tests — dynasty default 25-slot target,
  ESPN 14-slot default, 2-QB Superflex need, no DEF/K in dynasty, 3-WR need,
  ESPN DEF/K required, custom target override, TBD slot creation, confirmed slot,
  `confirm_draft_slot` updates, double-confirm rejected, invalid slot rejected.

### Draft slot strategy

The user's draft position in the Sleeper startup is not yet known. The recommended
workflow is:

1. Run the strategy creation skill now (slot TBD) to build 1-2 dynasty strategies.
2. At mock/live draft start, call `confirm_draft_slot` with the revealed slot to
   enable pick-number math and next-pick forecasting.
3. The `draft_init_session` MCP tool supports `user_slot=0` for the same TBD path.

### Strategy save paths

| Platform | Strategies | Logs |
|---|---|---|
| ESPN 16-team snake | `draft-context/espn_snake/strategies/` | `draft-context/espn_snake/logs/` |
| Sleeper 10-team dynasty | `draft-context/sleeper_dynasty/strategies/` | `draft-context/sleeper_dynasty/logs/` |
