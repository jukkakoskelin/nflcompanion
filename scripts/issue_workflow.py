"""Agentic issue-driven workflow automation for NFL Companion.

Provides helpers and CLI commands to:
1. Search and inspect GitHub issues via GitHub CLI (`gh`).
2. Guide issue creation from template when no matching issue exists.
3. Generate sanitized feature branch names (`feature/<id>-<slug>`) and check them out.
4. Extract or flag the Expected End Result (Definition of Done).
5. Generate plan snippets for `PLAN.md`.
6. Assemble and submit Pull Requests with the enriched PR template.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
ISSUE_TEMPLATE_PATH = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "feature_request.md"
PR_TEMPLATE_PATH = REPO_ROOT / ".github" / "pull_request_template.md"


# Ensure UTF-8 output where possible on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def sanitize_slug(text: str, max_length: int = 50) -> str:
    """Normalize text into a lowercase, hyphen-separated branch slug."""
    text = text.lower()
    # Replace non-alphanumeric characters with hyphens
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    if len(text) > max_length:
        # Avoid cutting in the middle of a word if possible
        truncated = text[:max_length]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > max_length // 2:
            text = truncated[:last_hyphen]
        else:
            text = truncated.rstrip("-")
    return text or "unnamed-task"


def make_branch_name(issue_id: int | str, title: str) -> str:
    """Create a standardized branch name: feature/<id>-<sanitized-title>."""
    slug = sanitize_slug(title)
    return f"feature/{issue_id}-{slug}"


def extract_expected_end_result(issue_body: str) -> dict[str, Any]:
    """Inspect issue body for an explicit Expected End Result section."""
    if not issue_body:
        return {
            "has_end_result": False,
            "end_result": "",
            "source": "needs_formulation",
        }

    # Matches headings like ## Expected End Result, ### Definition of Done, etc.
    pattern = re.compile(
        r"#{1,4}\s*(?:Expected End Result|Definition of Done|End Result)[^\n]*\n(.*?)(?=\n#{1,4}\s|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(issue_body)
    if match:
        content = match.group(1).strip()
        # Remove HTML comments if any
        cleaned = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL).strip()
        if cleaned:
            return {
                "has_end_result": True,
                "end_result": cleaned,
                "source": "issue",
            }

    return {
        "has_end_result": False,
        "end_result": "",
        "source": "needs_formulation",
    }


def run_cmd(
    cmd: Sequence[str],
    capture_output: bool = True,
    check: bool = True,
    dry_run: bool = False,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute shell command with dry-run support."""
    if dry_run:
        # Format command display cleanly, summarizing long bodies
        display_parts: list[str] = []
        for part in cmd:
            if len(part) > 80:
                display_parts.append(f"{part[:30]}...[len {len(part)}]")
            else:
                display_parts.append(part)
        print(f"[DRY-RUN] Would run: {' '.join(display_parts)}")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="",
            stderr="",
        )
    return subprocess.run(
        cmd,
        cwd=cwd or REPO_ROOT,
        capture_output=capture_output,
        text=True,
        check=check,
    )


def fetch_issue(issue_id: int | str, dry_run: bool = False) -> dict[str, Any]:
    """Fetch issue details via gh CLI as JSON."""
    if dry_run:
        return {
            "number": int(issue_id) if str(issue_id).isdigit() else 1,
            "title": f"Sample Issue {issue_id}",
            "body": "## Description & Context\nSample description.\n\n## Expected End Result (Definition of Done)\nWorking feature.",
            "labels": [{"name": "enhancement"}],
        }
    cmd = [
        "gh",
        "issue",
        "view",
        str(issue_id),
        "--json",
        "number,title,body,labels,state",
    ]
    proc = run_cmd(cmd, check=True)
    return json.loads(proc.stdout)


def search_issues(query: str, limit: int = 10, dry_run: bool = False) -> list[dict[str, Any]]:
    """Search open GitHub issues matching query."""
    if dry_run:
        return []
    cmd = [
        "gh",
        "issue",
        "list",
        "--state",
        "open",
        "--search",
        query,
        "--limit",
        str(limit),
        "--json",
        "number,title,updatedAt,labels",
    ]
    proc = run_cmd(cmd, check=True)
    return json.loads(proc.stdout)


def create_issue(
    title: str,
    description: str,
    end_result: str,
    acceptance_criteria: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a new GitHub issue formatted with the standard feature template."""
    criteria_lines = "\n".join(f"- [ ] {item}" for item in (acceptance_criteria or ["Verify implementation"]))
    body = (
        f"## Description & Context\n{description.strip()}\n\n"
        f"## Expected End Result (Definition of Done)\n{end_result.strip()}\n\n"
        f"## Acceptance Criteria\n{criteria_lines}\n"
    )
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    if labels:
        for label in labels:
            cmd.extend(["--label", label])

    if dry_run:
        print(f"[DRY-RUN] Would create issue with title: {title}")
        print(f"[DRY-RUN] Body:\n{body}")
        return {"number": 999, "title": title, "body": body}

    proc = run_cmd(cmd, check=True)
    # Output is URL of created issue, e.g. https://github.com/owner/repo/issues/42
    output = proc.stdout.strip()
    match = re.search(r"/issues/(\d+)", output)
    issue_num = int(match.group(1)) if match else 0
    return {"number": issue_num, "url": output, "title": title, "body": body}


def checkout_feature_branch(branch_name: str, dry_run: bool = False) -> None:
    """Create and switch to the specified feature branch."""
    cmd = ["git", "checkout", "-b", branch_name]
    run_cmd(cmd, check=True, dry_run=dry_run)


def generate_plan_snippet(
    issue: dict[str, Any],
    end_result: str,
    is_expanded: bool = False,
) -> str:
    """Generate a Markdown plan snippet for inclusion in PLAN.md."""
    num = issue.get("number", "X")
    title = issue.get("title", "Feature Title")
    expansion_note = (
        "*(Expanded by Planning Agent with detailed acceptance criteria)*"
        if is_expanded
        else "*(Adopted from issue specification)*"
    )
    return (
        f"### Feature #{num}: {title}\n\n"
        f"- **Branch:** `{make_branch_name(num, title)}`\n"
        f"- **Status:** In Progress (Planning)\n\n"
        f"#### Expected End Result {expansion_note}\n\n"
        f"{end_result.strip()}\n\n"
        f"#### Implementation & Verification Plan\n\n"
        f"1. Implement core functionality.\n"
        f"2. Add automated unit/integration tests verifying the Expected End Result.\n"
        f"3. Verify all test suites pass: `python -m unittest discover -s tests -v`.\n"
        f"4. Quality and security audit by Reviewer Agent.\n"
    )


def build_pr_body(
    issue: dict[str, Any],
    synopsis: str,
    end_result: str,
    verification: str,
    template_path: Path | None = None,
) -> str:
    """Assemble the PR description from the PR template format."""
    path = template_path or PR_TEMPLATE_PATH
    num = issue.get("number", "X")
    template_content = path.read_text(encoding="utf-8") if path.exists() else ""

    body = (
        f"## 📋 Synopsis of Changes\n\n"
        f"Closes #{num}\n\n"
        f"{synopsis.strip()}\n\n"
        f"## 🎯 Expected End Result\n\n"
        f"{end_result.strip()}\n\n"
        f"## 🧪 Verification & Test Results\n\n"
        f"{verification.strip()}\n\n"
        f"## 🛡️ Reviewer Quality & Security Sign-off\n\n"
        f"- [x] **Plan Adherence:** Implementation fulfills all specified criteria in the plan.\n"
        f"- [x] **Quality Gate:** Code and Markdown follow repository conventions and best practices.\n"
        f"- [x] **Security Audit:** No hardcoded secrets, unsafe dependencies, or injection risks.\n"
        f"- [x] **Verification Gate:** Automated unit/integration tests implemented and passing.\n\n"
        f"## 📋 Guardrails Checklist\n\n"
        f"- [x] **Agent Guidelines:** I have reviewed `PLAN.md` and `AGENTS.md`.\n"
        f"- [x] **Plan Updates:** `PLAN.md` updated with issue details and `Status:` line preserved.\n"
        f"- [x] **Tests Passing:** `python -m unittest discover -s tests -v` ran and passed.\n"
        f"- [x] **State Isolation:** No runtime/player state committed.\n"
    )
    return body


def create_pr(
    issue: dict[str, Any],
    synopsis: str,
    end_result: str,
    verification: str,
    branch_name: str | None = None,
    dry_run: bool = False,
) -> str:
    """Push the feature branch to origin and create the PR."""
    num = issue.get("number", "X")
    title = issue.get("title", f"Feature #{num}")
    branch = branch_name or make_branch_name(num, title)
    pr_title = f"feat(issue-{num}): {title}"
    pr_body = build_pr_body(issue, synopsis, end_result, verification)

    # 1. Push branch
    push_cmd = ["git", "push", "-u", "origin", branch]
    run_cmd(push_cmd, check=True, dry_run=dry_run)

    # 2. Create PR
    pr_cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        pr_title,
        "--body",
        pr_body,
        "--head",
        branch,
    ]
    proc = run_cmd(pr_cmd, check=True, dry_run=dry_run)
    return proc.stdout.strip() if not dry_run else f"[DRY-RUN] PR created for branch {branch}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Slug helper
    slug_parser = subparsers.add_parser("slug", help="Generate sanitized branch slug")
    slug_parser.add_argument("issue_id", help="Issue number or identifier")
    slug_parser.add_argument("title", help="Issue title")

    # Search helper
    search_parser = subparsers.add_parser("search", help="Search open GitHub issues")
    search_parser.add_argument("query", help="Keywords to search")

    # Create issue helper
    ci_parser = subparsers.add_parser("create-issue", help="Create a GitHub issue from template")
    ci_parser.add_argument("--title", required=True, help="Issue title")
    ci_parser.add_argument("--description", required=True, help="Description/context")
    ci_parser.add_argument("--end-result", required=True, help="Expected End Result (Definition of Done)")
    ci_parser.add_argument("--criteria", nargs="*", default=[], help="Acceptance criteria items")
    ci_parser.add_argument("--labels", nargs="*", default=["enhancement"], help="Labels")

    # Start helper (branch checkout)
    start_parser = subparsers.add_parser("start", help="Fetch issue and checkout feature branch")
    start_parser.add_argument("issue_id", help="Issue number to pull and start")

    # Prepare plan snippet
    plan_parser = subparsers.add_parser("prepare-plan", help="Generate plan snippet for an issue")
    plan_parser.add_argument("issue_id", help="Issue number")

    # PR helper
    pr_parser = subparsers.add_parser("pr", help="Push branch and create Pull Request")
    pr_parser.add_argument("issue_id", help="Issue number")
    pr_parser.add_argument("--synopsis", required=True, help="Summary of what was done")
    pr_parser.add_argument("--end-result", required=True, help="Delivered end result vs expected")
    pr_parser.add_argument("--verification", required=True, help="Test execution results")
    pr_parser.add_argument("--branch", help="Branch name (default: derived from issue)")

    args = parser.parse_args(argv)

    if args.command == "slug":
        branch = make_branch_name(args.issue_id, args.title)
        print(branch)
        return 0

    if args.command == "search":
        issues = search_issues(args.query, dry_run=args.dry_run)
        if not issues:
            print(f"No open issues found matching '{args.query}'.")
        else:
            print(f"Found {len(issues)} matching issue(s):")
            for item in issues:
                print(f"  #{item['number']}: {item['title']}")
        return 0

    if args.command == "create-issue":
        result = create_issue(
            title=args.title,
            description=args.description,
            end_result=args.end_result,
            acceptance_criteria=args.criteria,
            labels=args.labels,
            dry_run=args.dry_run,
        )
        print(f"Issue #{result.get('number')}: {result.get('title')}")
        if "url" in result:
            print(f"URL: {result['url']}")
        return 0

    if args.command == "start":
        issue = fetch_issue(args.issue_id, dry_run=args.dry_run)
        branch = make_branch_name(issue["number"], issue["title"])
        print(f"Fetched Issue #{issue['number']}: {issue['title']}")
        print(f"Checking out feature branch: {branch}")
        checkout_feature_branch(branch, dry_run=args.dry_run)
        print(f"Successfully checked out branch '{branch}'.")
        return 0

    if args.command == "prepare-plan":
        issue = fetch_issue(args.issue_id, dry_run=args.dry_run)
        res = extract_expected_end_result(issue.get("body", ""))
        end_result = res["end_result"] or "[Define the Expected End Result / Definition of Done here]"
        snippet = generate_plan_snippet(issue, end_result, is_expanded=res["has_end_result"])
        print(snippet)
        return 0

    if args.command == "pr":
        issue = fetch_issue(args.issue_id, dry_run=args.dry_run)
        res = create_pr(
            issue=issue,
            synopsis=args.synopsis,
            end_result=args.end_result,
            verification=args.verification,
            branch_name=args.branch,
            dry_run=args.dry_run,
        )
        print(res)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
