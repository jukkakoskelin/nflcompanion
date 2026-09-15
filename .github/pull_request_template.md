## 📋 Synopsis of Changes

<!-- Mention the related issue, e.g. Closes #123 -->
<!-- Concise summary of what was done, why, and architectural decisions -->

## 🎯 Expected End Result

<!-- State the Expected End Result (Definition of Done) defined in the issue or expanded by the Planning Agent -->
<!-- Explain how the delivered implementation satisfies this end result -->

## 🧪 Verification & Test Results

<!-- Detail how the changes were verified -->
<!-- Include commands executed (e.g. python -m unittest discover -s tests -v) and test outcomes -->

## 🛡️ Reviewer Quality & Security Sign-off

- [ ] **Plan & Result Adherence:** Verified implementation satisfies the plan and expected end result.
- [ ] **Code & Markdown Quality:** Clean, maintainable, follows repository patterns and formatting.
- [ ] **Security Audit:** No hardcoded secrets, unsafe dependency usage, or input injection risks.
- [ ] **Verification Rigor:** Automated unit/integration tests added and passing cleanly.

## 📋 Guardrails Checklist

Please ensure the following repository guardrails from `AGENTS.md` have been met before merging:

- [ ] **Agent Guidelines:** I have reviewed `PLAN.md` and `AGENTS.md` before making implementation changes.
- [ ] **Plan Updates:** If files under `src/`, key scripts, or `pyproject.toml` were modified, `PLAN.md` was updated in the same change.
- [ ] **Status Line:** If `PLAN.md` was updated, the `Status:` line was preserved or updated.
- [ ] **Tests Passing:** Installed package (`python -m pip install -e .`) and passed tests (`python -m unittest discover -s tests -v`).
- [ ] **State Isolation:** No runtime state or player snapshots under `state/` are included in the commits.
