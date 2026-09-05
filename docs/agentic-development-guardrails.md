# Agentic development guardrails

This repository now uses three lightweight guardrails for agentic development:

1. **Plan verification for implementation changes**  
   `.github/workflows/agentic-guardrails.yml` runs
   `scripts/check_agentic_guardrails.py` to ensure `PLAN.md` exists and that
   implementation changes under `src/`, `scripts/`, or `pyproject.toml` are
   accompanied by an update to `PLAN.md`.
2. **Automated test verification**  
   The same workflow runs `python -m unittest discover -s tests -v` so proposed
   changes continue to satisfy the repository's existing unit tests.
3. **Repository Copilot instructions**  
   `.github/copilot-instructions.md` tells agents to read the plan first, keep
   implementation changes paired with `PLAN.md`, and use the repository's
   existing install/test commands.

## Evaluated best practices

| Best practice | Selected? | Why |
| --- | --- | --- |
| Keep a repository plan artifact that is reviewed alongside code changes. | Yes | This repository already keeps `PLAN.md`, so requiring implementation changes to update it is a low-cost way to keep agent work tied to an explicit plan. |
| Validate implementation changes in CI with the repository's existing test suite. | Yes | The project already has a small `unittest` suite, so running it in GitHub Actions adds a direct correctness check without changing the test stack. |
| Put repository-specific agent instructions in `.github/copilot-instructions.md`. | Yes | This is a direct GitHub best practice for improving agent reliability, and it lets this repository encode the exact plan and test workflow agents should follow. |
| Keep automation least-privilege and read-only unless a write is necessary. | Yes | The new workflow only checks out the repository, runs a local script, installs the package, and executes tests; it does not need extra tokens or deployment permissions. |
| Preserve a human-readable verification artifact. | Yes | Updating `PLAN.md` keeps the implementation rationale in a durable repo file that reviewers can inspect during PR review. |
| Require human review before merging agent-authored changes. | Yes, by process rather than code | Pull requests already provide the repository's review boundary. This repository is small enough that mandatory PR review is a better fit than adding another approval system in code. |
| Require structured plan files, ADRs, or multiple review artifacts for every change. | No | That would be heavier than needed for a small repository with one main plan document and a compact codebase. |
| Add separate policy engines or external agent orchestration services. | No | The repository does not need that operational overhead yet; a local script plus GitHub Actions covers the stated issue with much less complexity. |
| Retain uploaded plans or generated reports as build artifacts in every workflow run. | No | The repository already stores the authoritative verification artifacts in version control, so extra artifact uploads would be redundant for now. |

## Why these guardrails fit this repository

- The codebase is small and Python-only, so a single workflow is enough.
- `PLAN.md` already exists and is the natural verification artifact to keep in
  sync with implementation work.
- The existing `unittest` coverage is modest but real, making CI verification a
  good incremental safeguard without introducing new tooling.

## Sources consulted

- GitHub Docs: [Responsible use of GitHub Copilot coding agent on GitHub.com](https://docs.github.com/en/copilot/responsible-use-of-github-copilot-features/responsible-use-of-github-copilot-coding-agent-on-githubcom)
- GitHub Docs: [Using GitHub Copilot to work on an issue](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/using-github-copilot-to-work-on-an-issue)
- Microsoft Learn: [GH-600 study guide](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/gh-600)
