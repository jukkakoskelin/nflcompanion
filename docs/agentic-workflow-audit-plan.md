# Agentic Workflow Audit & Implementation Record (Issue #46)

Status: implementation complete — gaps re-audited and addressed on the issue
46 feature branch.
Scope: re-audit the repository's existing agentic tooling against GitHub Copilot
cloud agent best practices and Google Antigravity skill/rule/hook best
practices, implement the confirmed gaps, and record the resulting state.

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
| Copilot cloud agent environment setup | `.github/workflows/copilot-setup-steps.yml` | Yes |
| Plan guardrail CI | [.github/workflows/agentic-guardrails.yml](../.github/workflows/agentic-guardrails.yml), [scripts/check_agentic_guardrails.py](../scripts/check_agentic_guardrails.py) | Yes |
| Issue-driven feature workflow | [scripts/issue_workflow.py](../scripts/issue_workflow.py), [.github/ISSUE_TEMPLATE/feature_request.md](../.github/ISSUE_TEMPLATE/feature_request.md), [.agents/skills/issue-workflow/SKILL.md](../.agents/skills/issue-workflow/SKILL.md) | Yes |
| Antigravity skills (progressive disclosure) | [.agents/skills/draft-strategy/SKILL.md](../.agents/skills/draft-strategy/SKILL.md), [.agents/skills/draft-companion/SKILL.md](../.agents/skills/draft-companion/SKILL.md), [.agents/skills/issue-workflow/SKILL.md](../.agents/skills/issue-workflow/SKILL.md) | Yes |
| Antigravity lifecycle hooks | [.agents/hooks.json](../.agents/hooks.json), [scripts/hooks/pre_invocation_trending.py](../scripts/hooks/pre_invocation_trending.py), [scripts/hooks/check_guardrails_stop.py](../scripts/hooks/check_guardrails_stop.py) | Yes |
| Standard MCP server (dual-harness) | [.agents/mcp_config.json](../.agents/mcp_config.json), [.vscode/mcp.json](../.vscode/mcp.json), `scripts/mcp_server.py` | Yes (configs aligned) |
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
2. **Environment setup file for Copilot cloud agent** —
   `.github/workflows/copilot-setup-steps.yml` uses `workflow_dispatch`, a job
   named `copilot-setup-steps`, Python 3.14, read-only repository permissions,
   and editable package installation. ✅ Compliant.
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
   ✅ Compliant. `.github/copilot-instructions.md` now delegates shared rules to
   `AGENTS.md` and retains only Copilot-surface-specific guidance, avoiding
   duplicated draft and issue workflow contracts.
3. **Hooks** (`.agents/hooks.json`): both registered hooks
   (`trending-context-injector` on `PreInvocation`, `guardrails-checker` on
   `Stop`) use the flat handler-array schema that the docs specify for
   `PreInvocation`/`Stop` events (no `matcher` needed, unlike
   `PreToolUse`/`PostToolUse`). The handler scripts' stdin/stdout contracts
   (`decision`/`reason` for `Stop`, `injectSteps` for `PreInvocation`) match
   the documented schema. ✅ Compliant.
4. **MCP configuration parity**: `.agents/mcp_config.json` and
   `.vscode/mcp.json` both register `nflcompanion` and `fetch`
   (`mcp-server-fetch`). ✅ Compliant.

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

## 5. Implemented changes

Files **created**:
- `.github/workflows/copilot-setup-steps.yml` — `workflow_dispatch`-triggered
   job named `copilot-setup-steps` that installs Python 3.14 and the package in
   editable mode for Copilot cloud-agent sessions.

Files **changed**:
- `.agents/mcp_config.json` — added the `fetch` MCP server entry so
   Antigravity and Copilot/VS Code expose the same MCP toolset.
- `.github/copilot-instructions.md` — points to `AGENTS.md` for shared rules
   and retains concise Copilot-specific MCP and setup guidance.

Files **preserved unchanged**:
- `AGENTS.md`
- `.agents/skills/draft-strategy/SKILL.md`, `.agents/skills/draft-companion/SKILL.md`, `.agents/skills/issue-workflow/SKILL.md`
- `.agents/hooks.json` and `scripts/hooks/*.py`
- `.github/workflows/agentic-guardrails.yml` and `scripts/check_agentic_guardrails.py`
- `scripts/issue_workflow.py` and `.github/ISSUE_TEMPLATE/feature_request.md`
- `antigravity-refactor-plan.md` and `docs/agentic-development-guardrails.md` (historical record)

## 6. Re-audit and acceptance results

- [x] Copilot cloud-agent setup workflow exists with the required trigger,
   setup job, Python version, read-only permissions, and editable install.
- [x] `.agents/mcp_config.json` and `.vscode/mcp.json` expose matching server
   names and commands, including `fetch`.
- [x] Shared rules have one canonical source in `AGENTS.md`; Copilot-specific
   instructions remain in `.github/copilot-instructions.md`.
- [x] Existing skills, hooks, guardrails, MCP server behavior, and issue
   workflow files remain intact.
- [x] Focused configuration tests pass, and the full unittest suite passes.
