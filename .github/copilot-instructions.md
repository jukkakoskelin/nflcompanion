# Copilot instructions

Follow `AGENTS.md` as the canonical source for repository-wide rules,
guardrails, testing, draft workflows, and issue-driven development.

For Copilot sessions specifically:

- Prefer the configured `nflcompanion` and `fetch` MCP servers for repository
  and draft workflows; do not replace the native draft MCP path with shell
  commands during an active draft.
- Keep responses bounded and evidence-based during live draft assistance, and
  require explicit confirmation before recording a user's pick.
- Use `.github/workflows/copilot-setup-steps.yml` when a Copilot cloud-agent
  environment needs to be initialized.


