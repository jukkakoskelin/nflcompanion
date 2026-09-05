# NFL Fantasy Draft Companion Plan

Status: planning  
Priority: draft-ready MVP for the Sleeper dynasty draft and ESPN 16-team snake
draft in the next few days

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

Next:

1. Add cheat-sheet import parsing and ambiguity reports.
2. Add league, strategy, roster, and append-only draft event Markdown schemas.
3. Add deterministic candidate scoring and a temporary canvas view.
4. Add an agent instruction contract that requires citations and confirmation
   before state mutation.
