# Antigravity & GitHub Copilot Dual-Compatibility Refactor Plan

## Executive Summary

The `nflcompanion` repository is an NFL fantasy draft companion that combines deterministic Python logic (state storage, snapshot normalization, snake-draft math, candidate recommendation, and pick recording) with agentic workflows (multi-agent strategy intake, player queries, live draft assistance, and plan guardrails).

Currently, all agentic integration in this repository is built exclusively for the **GitHub Copilot ecosystem**:
1. System instructions reside in `.github/copilot-instructions.md`.
2. Tool definitions, session hooks, and interactive canvases are implemented in Node.js using `@github/copilot-sdk/extension` (`.github/extensions/sleeper-player-data/extension.mjs`).
3. External MCP tools are configured using VS Code's proprietary schema in `.vscode/mcp.json`.
4. Multi-agent contracts in `docs/draft-strategy-agents/` are tracked as static prompt descriptions for sequential manual or simulated execution.
5. Plan guardrails in `.github/workflows/` and `scripts/check_agentic_guardrails.py` strictly bind code changes to `PLAN.md`.

This document defines an end-to-end refactoring strategy to make this repository **first-class and fully functional across both GitHub Copilot and Google Antigravity (AGY)** without duplicating business logic, breaking existing Copilot workflows, or adding unnecessary dependencies.

---

## Architectural Comparison: GitHub Copilot vs. Google Antigravity

| Feature Area | Current GitHub Copilot Implementation | Google Antigravity Capability | Dual-Compatibility Architecture |
| :--- | :--- | :--- | :--- |
| **System Rules & Instructions** | `.github/copilot-instructions.md` | `AGENTS.md`, `GEMINI.md`, or `.agents/rules/*.md` | Maintain canonical `AGENTS.md` at root; mirror/reference in `.github/copilot-instructions.md`. |
| **Tool Execution** | Proprietary `@github/copilot-sdk/extension` (Node.js) | Standard Model Context Protocol (MCP) via `mcp_config.json` | Build a native Python MCP server (`src/nflcompanion/mcp_server.py`) exposing state tools. Expose via both `.agents/mcp_config.json` and `.vscode/mcp.json`. |
| **Lifecycle Hooks & Context** | `onSessionStart` hook in `extension.mjs` (Node.js) injecting ephemeral context | `.agents/hooks.json` (`PreInvocation`, `PreToolUse`, `PostToolUse`, `Stop`) | Create `.agents/hooks.json` with a `PreInvocation` hook that runs a Python script to inject trending context. |
| **Multi-Agent Orchestration** | Markdown prompt contracts in `docs/draft-strategy-agents/` (manual/simulated) | Native subagents (`invoke_subagent`, `define_subagent`, `send_message`) | Package roles into Antigravity Skills (`.agents/skills/draft-strategy/SKILL.md`) that invoke specialized subagents. |
| **Interactive Canvas / UI** | `createCanvas` via `@github/copilot-sdk/extension` running internal Node HTTP server | Generative UI (interactive HTML widgets, standalone artifacts, or browser sidecars) | Decouple UI into a lightweight HTML/JS web server or Generative UI artifact. Usable by Copilot Canvas and Antigravity `/browser` or canvas widgets. |
| **Planning & Guardrails** | CI script `check_agentic_guardrails.py` requiring edits to `PLAN.md` | Antigravity Planning Mode (`implementation_plan.md` in brain artifacts) | Teach Antigravity in `AGENTS.md` to sync changes to `PLAN.md`; add a `PreToolUse` or `Stop` hook running the guardrail check locally. |
| **Progressive Disclosure** | None (full instructions loaded in context) | `.agents/skills/<name>/SKILL.md` (metadata loaded first, full skill loaded on demand) | Introduce structured skills under `.agents/skills/` for draft strategy and draft execution. |

---

## Key Refactoring Areas

### 1. Project Rules & Instructions (`AGENTS.md`)

#### The Problem
- GitHub Copilot reads `.github/copilot-instructions.md`.
- Antigravity automatically discovers `AGENTS.md` and `GEMINI.md` at the project root and in subdirectories, walking up from the current working directory. It does not automatically load `.github/copilot-instructions.md`.
- Having two disconnected files risks rule drift.

#### The Solution
1. Create `AGENTS.md` at the repository root as the canonical instruction file.
2. Update `.github/copilot-instructions.md` to align with `AGENTS.md` (or contain a directive to review `AGENTS.md`).
3. Add Antigravity-specific awareness of the repository's strict CI guardrails:
   - Any modification to files under `src/`, `scripts/fetch_sleeper_players.py`, `scripts/query_players.py`, `scripts/fetch_sleeper_trending.py`, `scripts/query_trending_players.py`, or `pyproject.toml` **must be accompanied by an update to `PLAN.md` with a valid `Status:` line**.

```markdown
<!-- Proposed AGENTS.md content -->
# NFL Companion Agent Guidelines

- Review `PLAN.md` before proposing or making implementation changes.
- GUARDRAIL ENFORCEMENT: When changing files under `src/`, `scripts/fetch_sleeper_players.py`, `scripts/query_players.py`, `scripts/fetch_sleeper_trending.py`, `scripts/query_trending_players.py`, or `pyproject.toml`, you MUST update `PLAN.md` in the same commit/change. Ensure the `Status:` line is preserved or updated.
- Install the package with `python -m pip install -e .` before running tests.
- Run tests with `python -m unittest discover -s tests -v`.
- Keep generated player snapshots under `state/players/` out of version control.
- Never record or commit a draft pick without explicit user confirmation.

## Multi-Agent Draft Strategy Flow
- Follow the four-role contract: Orchestrator, Interviewer, Validator, and Writer.
- Persist strategies through `scripts/create_draft_strategy.py` or `nflcompanion.state_store` so Markdown files and append-only creation logs stay synchronized.
- Obvious red flags (e.g. early kicker or defense) must be caught by validation before strategy persistence.
```

---

### 2. Standard MCP Server (Decoupling from `@github/copilot-sdk/extension`)

#### The Problem
- `.github/extensions/sleeper-player-data/extension.mjs` is tied to the proprietary `@github/copilot-sdk/extension` package. Antigravity cannot execute or discover this extension.
- Furthermore, `extension.mjs` duplicates player filtering, JSON parsing, and trending aggregation logic that already exists in Python in `src/nflcompanion/state_store.py` and `scripts/`.
- In `.vscode/mcp.json`, the configuration uses VS Code's schema (`"mcp": { "servers": ... }`) rather than the standard MCP server schema.

#### The Solution
1. **Implement a native Python MCP Server** (`src/nflcompanion/mcp_server.py` or `scripts/mcp_server.py`):
   - Expose the core tools via standard MCP over stdio (using the official Python `mcp` SDK or a lightweight stdio JSON-RPC loop):
     - `sleeper_ensure_player_state`: Ensures snapshot exists or triggers fresh download.
     - `sleeper_query_players`: Queries local player snapshot by name, position, team, status.
     - `sleeper_query_trending_players`: Queries local add/drop trends.
     - `draft_init_session`: Initializes a draft session.
     - `draft_recommend_candidates`: Deterministically scores 2–4 candidates.
     - `draft_record_pick`: Appends confirmed user selection (requires explicit `confirmed: true`).
     - `draft_next_pick_preview`: Displays upcoming draft targets and availability estimates.
2. **Configure for Antigravity**:
   - Create `.agents/mcp_config.json` (or bundle in `.agents/plugins/nflcompanion/mcp_config.json`):
     ```json
     {
       "mcpServers": {
         "nflcompanion": {
           "command": "python",
           "args": ["scripts/mcp_server.py"]
         },
         "fetch": {
           "command": "uvx",
           "args": ["mcp-server-fetch"]
         }
       }
     }
     ```
3. **Configure for VS Code / Copilot**:
   - Update `.vscode/mcp.json` so VS Code and Copilot also connect to the same Python MCP server:
     ```json
     {
       "mcp": {
         "servers": {
           "nflcompanion": {
             "command": "python",
             "args": ["scripts/mcp_server.py"]
           },
           "fetch": {
             "command": "uvx",
             "args": ["mcp-server-fetch"]
           }
         }
       }
     }
     ```
4. **Outcome**:
   - Both Antigravity and Copilot have access to the exact same tools.
   - Code duplication between JavaScript and Python is eliminated.
   - The `.github/extensions/` file can either be retired or kept solely for Copilot Workspace canvas backwards-compatibility.

---

### 3. Lifecycle Hooks & Context Injection (`.agents/hooks.json`)

#### The Problem
- In Copilot, `extension.mjs` runs an `onSessionStart` hook that calls Sleeper's trending API and injects the top adds and drops into the conversation context as ephemeral text.
- Antigravity does not execute Copilot extension hooks.

#### The Solution
- Antigravity provides a standard lifecycle hook mechanism via `.agents/hooks.json`.
- Implement a `PreInvocation` hook and an optional `Stop` / `PreToolUse` safety gate:

```json
{
  "trending-context-injector": {
    "PreInvocation": [
      {
        "type": "command",
        "command": "python scripts/hooks/pre_invocation_trending.py",
        "timeout": 15
      }
    ]
  },
  "guardrails-checker": {
    "Stop": [
      {
        "type": "command",
        "command": "python scripts/hooks/check_guardrails_stop.py",
        "timeout": 10
      }
    ]
  }
}
```

- **`scripts/hooks/pre_invocation_trending.py`**:
  - Reads input from `stdin` (contains session metadata).
  - Queries `state_store.py` for latest trending players (or refreshes if older than threshold).
  - Emits JSON to `stdout` conforming to Antigravity's `PreInvocation` contract:
    ```json
    {
      "injectSteps": [
        {
          "ephemeralMessage": "Sleeper trending players (last 24h): Top adds: ... Top drops: ... Use sleeper_query_trending_players for details."
        }
      ]
    }
    ```
- **`scripts/hooks/check_guardrails_stop.py`**:
  - Checks if git status has uncommitted or modified implementation files without a corresponding change to `PLAN.md`.
  - If a violation exists, returns `{"decision": "continue", "reason": "Implementation files were modified without updating PLAN.md. Please update PLAN.md before concluding."}`.
  - This prevents an Antigravity session from finishing with broken guardrails!

---

### 4. Skills & Native Subagent Delegation

#### The Problem
- `docs/draft-strategy-agents/` documents 5 agent roles (`orchestrator`, `interviewer`, `validator`, `evaluator`, `writer`) and `espn-strategy-agent.md`.
- In Copilot, these are manual prompt instructions or simulated via Python scripts because Copilot does not have native dynamic multi-agent delegation in the same way.
- In Antigravity, multi-agent workflows can be executed autonomously using `invoke_subagent` and `define_subagent`.

#### The Solution
1. **Retain `docs/draft-strategy-agents/`**:
   - Keep these files as the platform-agnostic prompt specifications for both tools.
2. **Create Antigravity Skills (`.agents/skills/`)**:
   - **`.agents/skills/draft-strategy/SKILL.md`**:
     - Teaches Antigravity how to run the multi-agent strategy creation workflow.
     - Uses `define_subagent` to spawn specialized roles (`interviewer`, `validator`, `evaluator`, `writer`) using the contracts in `docs/draft-strategy-agents/`.
     - Uses Antigravity's interactive `ask_question` tool for the intake questionnaire when running in conversational mode.
   - **`.agents/skills/draft-companion/SKILL.md`**:
     - Teaches Antigravity how to operate during a live draft (15-second response budget, deterministic candidate scoring, next-pick forecasting, and mandatory confirmation before recording picks).

---

### 5. Interactive Canvases & Generative UI

#### The Problem
- `extension.mjs` defines a Copilot Canvas (`createCanvas`) that spins up a local Node HTTP server on a random port to render an interactive HTML table for player filtering.
- Antigravity does not use Copilot Canvas APIs.

#### The Solution
1. **Decouple the Web UI**:
   - Move the HTML/JS frontend into a clean standalone module (e.g. `src/nflcompanion/web/` or a static HTML/JS template).
   - Provide a simple entry point: `python -m nflcompanion.web` or an endpoint in the local server.
2. **Antigravity Generative UI Integration**:
   - In Antigravity, we can render rich interactive controls directly inside the conversation or as standalone artifacts using the `generative_ui` skill.
   - The agent can output an interactive table/widget showing candidate rankings, factor scores, and roster needs directly in the chat or artifact pane.
3. **Dual Support**:
   - Copilot: `extension.mjs` (or VS Code webview) can embed the local server.
   - Antigravity: Viewable via Antigravity 2.0 sidecar/browser or inline Generative UI widgets.

---

### 6. Planning Mode & CI Guardrail Harmonization

#### The Problem
- The repository has an automated CI check (`.github/workflows/agentic-guardrails.yml` -> `scripts/check_agentic_guardrails.py`) that fails if files in `src/`, `pyproject.toml`, or certain scripts are modified without updating `PLAN.md` (and ensuring `Status:` is present).
- Antigravity has its own native Planning Mode that creates `implementation_plan.md` in `<appDataDir>/brain/<conversation-id>/`.
- An Antigravity agent might assume its internal `implementation_plan.md` is sufficient and forget to edit `PLAN.md`, causing CI to fail when changes are committed.

#### The Solution
1. Explicitly document in `AGENTS.md` that repo-level planning MUST be reflected in `PLAN.md`.
2. Provide a helper script or guideline: when Antigravity creates or modifies an `implementation_plan.md`, it must also update `PLAN.md` with the current status, summary of work, and delivery checklist.
3. Implement the `Stop` hook in `.agents/hooks.json` to verify `python scripts/check_agentic_guardrails.py` locally before completing turns that touch implementation code.

---

## Directory Layout: Before vs. After

```text
Before (Copilot-Only):
nflcompanion/
├── .github/
│   ├── copilot-instructions.md            # Only read by Copilot
│   ├── extensions/
│   │   └── sleeper-player-data/
│   │       └── extension.mjs              # Proprietary Copilot SDK (Node.js)
│   └── workflows/
│       └── agentic-guardrails.yml
├── .vscode/
│   └── mcp.json                           # VS Code format only
├── docs/
│   ├── agentic-development-guardrails.md
│   └── draft-strategy-agents/             # Static prompt docs
├── scripts/                               # Python utility scripts
├── src/nflcompanion/                      # Core business logic
└── PLAN.md                                # Authoritative planning file

After (Dual-Compatible with Antigravity & Copilot):
nflcompanion/
├── .agents/                               # [NEW] Antigravity customization root
│   ├── mcp_config.json                    # [NEW] Antigravity MCP configuration
│   ├── hooks.json                         # [NEW] Lifecycle hooks (PreInvocation, Stop)
│   └── skills/
│       ├── draft-companion/
│       │   └── SKILL.md                   # [NEW] Antigravity draft live-session skill
│       └── draft-strategy/
│           └── SKILL.md                   # [NEW] Antigravity multi-agent strategy skill
├── .github/
│   ├── copilot-instructions.md            # Aligned with AGENTS.md
│   ├── extensions/
│   │   └── sleeper-player-data/
│   │       └── extension.mjs              # Kept for legacy Copilot Canvas or refactored
│   └── workflows/
│       └── agentic-guardrails.yml
├── .vscode/
│   └── mcp.json                           # Updated with standard Python MCP server
├── docs/
│   ├── agentic-development-guardrails.md
│   └── draft-strategy-agents/             # Shared multi-agent prompt contracts
├── scripts/
│   ├── hooks/
│   │   ├── pre_invocation_trending.py     # [NEW] Hook script for Antigravity
│   │   └── check_guardrails_stop.py       # [NEW] Hook script for local CI gate
│   ├── mcp_server.py                      # [NEW] Unified Python MCP server entry point
│   └── ... (existing scripts)
├── src/nflcompanion/
│   ├── mcp_server.py                      # [NEW] Fast/stdio MCP server implementation
│   └── ... (existing modules)
├── AGENTS.md                              # [NEW] Canonical rules for Antigravity & Copilot
├── PLAN.md                                # Maintained for CI & agentic planning
└── pyproject.toml                         # Updated with optional 'mcp' dependency
```

---

## Detailed Implementation Steps & Specifications

### Phase 1: Canonical Rules & Instruction Alignment
1. **Create `AGENTS.md`** at root.
   - Includes test requirements (`python -m unittest discover -s tests -v`).
   - Includes install command (`python -m pip install -e .`).
   - Includes explicit `PLAN.md` guardrail requirements.
   - Outlines draft state boundaries (`state/` directory, human confirmation requirement).
2. **Update `.github/copilot-instructions.md`**.
   - Ensure text stays synchronized with `AGENTS.md`.

### Phase 2: Python-Based Standard MCP Server
1. **Add Python MCP Server (`src/nflcompanion/mcp_server.py`)**:
   - Use the standard `mcp` library or a zero-dependency lightweight stdio JSON-RPC handler.
   - Wrap existing functions in `src/nflcompanion/state_store.py` and `src/nflcompanion/draft_companion.py`.
   - Implement tools:
     - `sleeper_ensure_player_state(refresh: bool = False)`
     - `sleeper_query_players(name, position, team, activeOnly, limit)`
     - `sleeper_query_trending_players(direction, position, team, limit, refresh)`
     - `draft_init_session(league_id, season, draft_style, team_count, user_slot, ...)`
     - `draft_recommend_candidates(league_id, season, candidates)`
     - `draft_record_pick(league_id, season, provider_id, full_name, confirmed, ...)`
     - `draft_next_pick_preview(league_id, season)`
2. **Expose MCP Server**:
   - Create entry point `scripts/mcp_server.py`.
   - Update `pyproject.toml` dependencies (e.g. `mcp>=1.0.0` or keep optional).
3. **Configure MCP for Both Platforms**:
   - Add `.agents/mcp_config.json` for Antigravity.
   - Update `.vscode/mcp.json` for GitHub Copilot / VS Code.

### Phase 3: Antigravity Lifecycle Hooks
1. **Create `scripts/hooks/pre_invocation_trending.py`**:
   - Run before each agent turn.
   - Check if trending data is older than 15 minutes.
   - Fetch fresh snapshot if needed and output top 10 adds/drops as an ephemeral message.
2. **Create `scripts/hooks/check_guardrails_stop.py`**:
   - Run on `Stop` event.
   - Run `check_agentic_guardrails.py`.
   - If violations exist, return `decision: "continue"` with reason.
3. **Add `.agents/hooks.json`**:
   - Wire up `PreInvocation` and `Stop` hooks.

### Phase 4: Antigravity Skills for Multi-Agent Workflows
1. **Create `.agents/skills/draft-strategy/SKILL.md`**:
   - Description: "Use this skill when creating, reviewing, or testing a new fantasy draft strategy for ESPN snake or Sleeper dynasty leagues."
   - Instructions for orchestrating the multi-agent flow:
     - Interviewing the user using `ask_question` or interactive chat prompts.
     - Spawning subagents (`validator`, `evaluator`, `writer`) using `invoke_subagent` and contracts in `docs/draft-strategy-agents/`.
     - Invoking `scripts/create_draft_strategy.py` to persist final verified output.
2. **Create `.agents/skills/draft-companion/SKILL.md`**:
   - Description: "Use this skill during an active fantasy draft to evaluate candidates, record picks, and preview upcoming picks within a 15-second budget."
   - Instructions for fast-lane recommendations, strictly adhering to the 15-second response budget, deterministic scoring, and requiring explicit user confirmation before recording picks.

### Phase 5: UI & Canvas Modernization
1. **Extract UI components**:
   - Decouple the HTML renderer in `extension.mjs` into a reusable component in Python or static web asset.
2. **Provide Dual UI Access**:
   - Copilot: Maintain canvas view via `extension.mjs`.
   - Antigravity: Support Generative UI artifacts or local server preview via Antigravity browser tooling (`/browser`).

### Phase 6: Automated Testing & Verification
1. **Unit Tests**:
   - Add tests for `mcp_server.py` and hook scripts in `tests/`.
   - Verify `check_agentic_guardrails.py` passes with the new files.
2. **End-to-End Verification**:
   - Test MCP tool invocation via stdio JSON-RPC.
   - Test Antigravity hook execution via mock stdin/stdout payloads.
   - Verify CI workflow continues to pass cleanly on GitHub Actions.

---

## Risk Assessment & Mitigation

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Breaking existing GitHub Copilot extension** | High for Copilot users | Keep `.github/extensions/` and `.github/copilot-instructions.md` intact; ensure all Antigravity additions are additive under `.agents/` and `AGENTS.md`. |
| **Guardrail CI failures during development** | Medium | Any change that touches `src/` or `pyproject.toml` must update `PLAN.md` in the same commit. Add the Antigravity `Stop` hook to catch this before committing. |
| **MCP Dependency bloat in Python** | Low | Implement the Python MCP server using standard library `json` and `sys.stdin`/`sys.stdout` (or the official `mcp` SDK as an optional dependency `pip install -e .[mcp]`). |
| **Windows vs POSIX script paths** | Low | Ensure hook commands in `hooks.json` use portable commands (`python scripts/...` rather than `sh ./scripts/...`) to run reliably across Windows, macOS, and Linux. |
