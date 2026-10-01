# Agentic Workflow Audit & Future Implementation Plan (Issue #44)

Status: plan only — no implementation performed in this change.
Scope: assess the repository's existing agentic tooling against GitHub Copilot
cloud agent best practices and Google Antigravity skill/rule/hook best
practices, then define what should be created, changed, or preserved in a
follow-up implementation issue.

Sources consulted:
- GitHub Docs: [Using GitHub Copilot cloud agent to improve a project](https://docs.github.com/en/copilot/tutorials/cloud-agent/improve-a-project)
- Google Antigravity Docs: [Agent skills](https://antigravity.google/docs/skills/)
- Google Antigravity Docs: [Rules](https://antigravity.google/docs/rules/)
- Google Antigravity Docs: [Lifecycle hooks](https://antigravity.google/docs/hooks/)

## 1. Current state inventory

| Area | File(s) | Present? |
| --- | --- | --- |
| Copilot custom instructions | [.github/copilot-instructions.md](../.github/copilot-instructions.md) | Yes |
| Cross-harness rules file | [AGENTS.md](../AGENTS.md) | Yes |
| Copilot cloud agent environment setup | `.github/workflows/copilot-setup-steps.yml` | **No** |
| Plan guardrail CI | [.github/workflows/agentic-guardrails.yml](../.github/workflows/agentic-guardrails.yml), [scripts/check_agentic_guardrails.py](../scripts/check_agentic_guardrails.py) | Yes |
| Issue-driven feature workflow | [scripts/issue_workflow.py](../scripts/issue_workflow.py), [.github/ISSUE_TEMPLATE/feature_request.md](../.github/ISSUE_TEMPLATE/feature_request.md), [.agents/skills/issue-workflow/SKILL.md](../.agents/skills/issue-workflow/SKILL.md) | Yes |
| Antigravity skills (progressive disclosure) | [.agents/skills/draft-strategy/SKILL.md](../.agents/skills/draft-strategy/SKILL.md), [.agents/skills/draft-companion/SKILL.md](../.agents/skills/draft-companion/SKILL.md), [.agents/skills/issue-workflow/SKILL.md](../.agents/skills/issue-workflow/SKILL.md) | Yes |
| Antigravity lifecycle hooks | [.agents/hooks.json](../.agents/hooks.json), [scripts/hooks/pre_invocation_trending.py](../scripts/hooks/pre_invocation_trending.py), [scripts/hooks/check_guardrails_stop.py](../scripts/hooks/check_guardrails_stop.py) | Yes |
| Standard MCP server (dual-harness) | [.agents/mcp_config.json](../.agents/mcp_config.json), [.vscode/mcp.json](../.vscode/mcp.json), `scripts/mcp_server.py` | Yes (configs drifted — see §3) |
| Legacy Copilot-only canvas extension | `.github/extensions/sleeper-player-data/extension.mjs` | Yes (Copilot-only, no Antigravity equivalent) |

The repository already implemented most of the dual-compatibility work
described in [antigravity-refactor-plan.md](../antigravity-refactor-plan.md)
(AGENTS.md, `.agents/skills/`, `.agents/hooks.json`, `.agents/mcp_config.json`,
`scripts/hooks/`, `scripts/mcp_server.py`). This plan audits that prior work
against the two reference docs cited in issue #44 and catches what still
needs attention, rather than re-proposing work already done.

## 2. GitHub Copilot best-practice assessment

Per the cloud-agent "improve a project" tutorial:

1. **Custom instructions exist** (`.github/copilot-instructions.md` and
   `AGENTS.md`). ✅ Compliant.
2. **Environment setup file for Copilot cloud agent** — the tutorial calls for
   `.github/workflows/copilot-setup-steps.yml` with a `workflow_dispatch`
   trigger and a job named `copilot-setup-steps` so the cloud agent can
   pre-install dependencies. This file **does not exist**. ❌ Gap.
3. **Technical-debt discovery → issue creation → delegate to Copilot → review
   PR** is a process, not a file, and is already supported structurally by
   `scripts/issue_workflow.py` (`search`, `create-issue`, `start`, `pr`
   subcommands) and the issue/PR templates. ✅ Process already supported.

## 3. Google Antigravity best-practice assessment

Per the Skills, Rules, and Hooks docs:

1. **Skills** (`.agents/skills/<name>/SKILL.md`) all use the required YAML
   frontmatter (`name`, `description`) and are each scoped to one workflow
   (draft-strategy, draft-companion, issue-workflow). ✅ Compliant.
2. **Rules**: all repo-wide guidance lives in root `AGENTS.md`, which the docs
   confirm is the correct `always_on` location when frontmatter isn't needed.
   ✅ Compliant for current size. Flagged as a **watch item**: `AGENTS.md` plus
   the loaded `.github/copilot-instructions.md` duplicate content (draft
   companion rules, issue workflow rules) almost verbatim. Antigravity's
   20,000-token aggregate rules budget and GitHub's single-source-of-truth
   goal both favor removing duplication before either file grows further.
3. **Hooks** (`.agents/hooks.json`): both registered hooks
   (`trending-context-injector` on `PreInvocation`, `guardrails-checker` on
   `Stop`) use the flat handler-array schema that the docs specify for
   `PreInvocation`/`Stop` events (no `matcher` needed, unlike
   `PreToolUse`/`PostToolUse`). The handler scripts' stdin/stdout contracts
   (`decision`/`reason` for `Stop`, `injectSteps` for `PreInvocation`) match
   the documented schema. ✅ Compliant.
4. **MCP config drift**: `.agents/mcp_config.json` registers only the
   `nflcompanion` server, while `.vscode/mcp.json` registers `nflcompanion`
   **and** `fetch` (`mcp-server-fetch`). Antigravity users therefore lack the
   `fetch` MCP tool that Copilot/VS Code users have. ❌ Gap (config drift).

## 4. Other inconsistencies identified

- `.github/extensions/sleeper-player-data/extension.mjs` remains a
  Copilot-only canvas (Node.js, `@github/copilot-sdk/extension`). Antigravity
  has no equivalent generative UI/sidecar wiring, so the interactive player
  table is Copilot-exclusive. This was an accepted, documented trade-off in
  `antigravity-refactor-plan.md` (Phase 5, not yet executed), not a new
  inconsistency — carried forward here for visibility.
- No `.github/instructions/**/*-instructions.md` directory is used; this is
  acceptable since GitHub's docs only require *at least one* of
  `copilot-instructions.md` or `AGENTS.md` to exist.

## 5. Proposed future implementation (for a follow-up issue)

Files to **create**:
- `.github/workflows/copilot-setup-steps.yml` — `workflow_dispatch`-triggered
  job named `copilot-setup-steps` that runs `python -m pip install -e .` (and
  installs test dependencies) so Copilot cloud agent sessions start with the
  environment ready.

Files to **change**:
- `.agents/mcp_config.json` — add the `fetch` MCP server entry so Antigravity
  and Copilot/VS Code expose the same MCP toolset.
- `.github/copilot-instructions.md` — reduce duplication by pointing to
  `AGENTS.md` as the canonical source for shared rules (draft recording
  confirmation, guardrail enforcement, draft companion MCP-only execution),
  keeping only Copilot-surface-specific notes (if any) inline.

Files to **preserve unchanged** (already compliant, no action needed):
- `AGENTS.md`
- `PLAN.md`
- `.agents/skills/draft-strategy/SKILL.md`, `.agents/skills/draft-companion/SKILL.md`, `.agents/skills/issue-workflow/SKILL.md`
- `.agents/hooks.json` and `scripts/hooks/*.py`
- `.github/workflows/agentic-guardrails.yml` and `scripts/check_agentic_guardrails.py`
- `scripts/issue_workflow.py` and `.github/ISSUE_TEMPLATE/feature_request.md`
- `antigravity-refactor-plan.md` and `docs/agentic-development-guardrails.md` (historical record)

## 6. Acceptance criteria for this issue

- [x] `PLAN.md` is intact (not modified by this change).
- [x] This new markdown file documents the audit and future plan.
- [x] No other files in the repository are changed by this issue.
