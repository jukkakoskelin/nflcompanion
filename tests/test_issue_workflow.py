"""Tests for scripts/issue_workflow.py."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.issue_workflow import (
    build_pr_body,
    create_issue,
    create_pr,
    extract_expected_end_result,
    fetch_issue,
    generate_plan_snippet,
    main,
    make_branch_name,
    sanitize_slug,
)


class IssueWorkflowTests(unittest.TestCase):
    def test_sanitize_slug_simple(self) -> None:
        self.assertEqual(
            sanitize_slug("Add Dynasty Trade Calculator"),
            "add-dynasty-trade-calculator",
        )

    def test_sanitize_slug_special_characters(self) -> None:
        raw = "Fix: handle [broken] Sleeper API/URL & 500 error!"
        self.assertEqual(
            sanitize_slug(raw),
            "fix-handle-broken-sleeper-api-url-500-error",
        )

    def test_sanitize_slug_consecutive_spaces_and_hyphens(self) -> None:
        self.assertEqual(
            sanitize_slug("  multiple   spaces --- and --- hyphens  "),
            "multiple-spaces-and-hyphens",
        )

    def test_sanitize_slug_empty_fallback(self) -> None:
        self.assertEqual(sanitize_slug("!@#$%^&*()"), "unnamed-task")

    def test_sanitize_slug_length_limit(self) -> None:
        long_title = "This is an extraordinarily long title that should be safely truncated without trailing hyphen"
        slug = sanitize_slug(long_title, max_length=30)
        self.assertLessEqual(len(slug), 30)
        self.assertFalse(slug.endswith("-"))

    def test_make_branch_name(self) -> None:
        self.assertEqual(
            make_branch_name(42, "Player Matchup Analyzer"),
            "feature/42-player-matchup-analyzer",
        )
        self.assertEqual(
            make_branch_name("108", "Export Draft CSV"),
            "feature/108-export-draft-csv",
        )

    def test_extract_expected_end_result_found(self) -> None:
        body = (
            "## Description & Context\n"
            "We need a trade calculator.\n\n"
            "## Expected End Result (Definition of Done)\n"
            "A CLI tool that evaluates fantasy trade values for 2026 dynasty.\n\n"
            "## Acceptance Criteria\n"
            "- [ ] Runs in < 1s\n"
        )
        res = extract_expected_end_result(body)
        self.assertTrue(res["has_end_result"])
        self.assertEqual(res["source"], "issue")
        self.assertIn("A CLI tool that evaluates fantasy trade values", res["end_result"])

    def test_extract_expected_end_result_strips_html_comments(self) -> None:
        body = (
            "## Expected End Result\n"
            "<!-- Some comment -->\n"
            "Working API endpoint returning JSON.\n"
        )
        res = extract_expected_end_result(body)
        self.assertTrue(res["has_end_result"])
        self.assertEqual(res["end_result"], "Working API endpoint returning JSON.")

    def test_extract_expected_end_result_missing(self) -> None:
        body = "## Description\nJust a simple bug description with no end result."
        res = extract_expected_end_result(body)
        self.assertFalse(res["has_end_result"])
        self.assertEqual(res["source"], "needs_formulation")
        self.assertEqual(res["end_result"], "")

    def test_extract_expected_end_result_empty_body(self) -> None:
        res = extract_expected_end_result("")
        self.assertFalse(res["has_end_result"])
        self.assertEqual(res["end_result"], "")

    def test_generate_plan_snippet_adopted(self) -> None:
        issue = {"number": 15, "title": "Draft Recap Generator"}
        end_result = "Script generating Markdown recap."
        snippet = generate_plan_snippet(issue, end_result, is_expanded=False)
        self.assertIn("Feature #15: Draft Recap Generator", snippet)
        self.assertIn("feature/15-draft-recap-generator", snippet)
        self.assertIn("Script generating Markdown recap.", snippet)
        self.assertIn("*(Adopted from issue specification)*", snippet)

    def test_generate_plan_snippet_expanded(self) -> None:
        issue = {"number": 16, "title": "Taxi Squad Sync"}
        end_result = "Syncs taxi slots."
        snippet = generate_plan_snippet(issue, end_result, is_expanded=True)
        self.assertIn("*(Expanded by Planning Agent with detailed acceptance criteria)*", snippet)

    def test_build_pr_body_structure(self) -> None:
        issue = {"number": 22, "title": "Support Superflex Mode"}
        body = build_pr_body(
            issue=issue,
            synopsis="Added superflex weighting to draft companion.",
            end_result="Draft companion correctly rates second QB.",
            verification="100% tests pass including test_superflex.py.",
        )
        self.assertIn("Closes #22", body)
        self.assertIn("## 📋 Synopsis of Changes", body)
        self.assertIn("Added superflex weighting", body)
        self.assertIn("## 🎯 Expected End Result", body)
        self.assertIn("Draft companion correctly rates second QB.", body)
        self.assertIn("## 🧪 Verification & Test Results", body)
        self.assertIn("100% tests pass", body)
        self.assertIn("## 🛡️ Reviewer Quality & Security Sign-off", body)
        self.assertIn("## 📋 Guardrails Checklist", body)

    def test_create_issue_dry_run(self) -> None:
        res = create_issue(
            title="feat: add waiver wire assistant",
            description="Track weekly waiver targets.",
            end_result="CLI command listing top waiver adds.",
            acceptance_criteria=["Reports FAAB budget", "Filters owned players"],
            labels=["enhancement"],
            dry_run=True,
        )
        self.assertEqual(res["number"], 999)
        self.assertIn("Track weekly waiver targets", res["body"])
        self.assertIn("CLI command listing top waiver adds", res["body"])
        self.assertIn("Reports FAAB budget", res["body"])

    def test_fetch_issue_dry_run(self) -> None:
        issue = fetch_issue(50, dry_run=True)
        self.assertEqual(issue["number"], 50)
        self.assertIn("Sample Issue 50", issue["title"])

    def test_create_pr_dry_run(self) -> None:
        issue = {"number": 33, "title": "Fix Bye Week Calculations"}
        result = create_pr(
            issue=issue,
            synopsis="Fixed bye week lookup",
            end_result="Bye weeks display accurately",
            verification="Unit tests pass",
            dry_run=True,
        )
        self.assertIn("[DRY-RUN]", result)

    def test_cli_slug_command(self) -> None:
        with patch("sys.stdout") as mock_stdout:
            exit_code = main(["slug", "77", "Add Dynasty Dashboard"])
            self.assertEqual(exit_code, 0)

    def test_cli_dry_run_start_command(self) -> None:
        exit_code = main(["--dry-run", "start", "10"])
        self.assertEqual(exit_code, 0)

    def test_cli_dry_run_prepare_plan_command(self) -> None:
        exit_code = main(["--dry-run", "prepare-plan", "10"])
        self.assertEqual(exit_code, 0)

    def test_cli_dry_run_pr_command(self) -> None:
        exit_code = main([
            "--dry-run",
            "pr",
            "10",
            "--synopsis",
            "Implemented feature",
            "--end-result",
            "Feature is operational",
            "--verification",
            "All unit tests pass",
        ])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
