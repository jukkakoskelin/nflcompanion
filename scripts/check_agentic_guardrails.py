"""Verify lightweight plan guardrails for agentic development."""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
from pathlib import Path

IMPLEMENTATION_PATTERNS = ("src/**", "scripts/**", "pyproject.toml")
IMPLEMENTATION_EXEMPTIONS = {"scripts/check_agentic_guardrails.py"}
ZERO_SHA = "0" * 40


def normalize_git_path(path: Path | str) -> str:
    return Path(path).as_posix().removeprefix("./")


def file_matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def changed_files(base_ref: str, head_ref: str) -> list[str]:
    if not base_ref or base_ref == ZERO_SHA:
        parent_result = subprocess.run(
            ["git", "rev-list", "--max-count=1", "--parents", head_ref],
            check=True,
            capture_output=True,
            text=True,
        )
        revisions = parent_result.stdout.split()
        if len(revisions) > 1:
            base_ref = revisions[1]
        else:
            command = ["git", "ls-tree", "-r", "--name-only", head_ref]
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            return [line for line in result.stdout.splitlines() if line]
    command = ["git", "diff", "--name-only", base_ref, head_ref]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def verify_plan(plan_path: Path) -> list[str]:
    violations: list[str] = []
    normalized_plan_path = normalize_git_path(plan_path)
    if not plan_path.exists():
        return [f"Missing required plan artifact: {normalized_plan_path}"]
    plan_text = plan_path.read_text(encoding="utf-8")
    if "Status:" not in plan_text:
        violations.append(f"Plan artifact {normalized_plan_path} must include a Status line")
    return violations


def verify_guardrails(base_ref: str, head_ref: str, plan_path: Path) -> list[str]:
    violations = verify_plan(plan_path)
    files = changed_files(base_ref, head_ref)
    normalized_plan_path = normalize_git_path(plan_path)
    implementation_files = [
        path
        for path in files
        if file_matches(path, IMPLEMENTATION_PATTERNS) and path not in IMPLEMENTATION_EXEMPTIONS
    ]
    if implementation_files and normalized_plan_path not in files:
        violations.append(
            "Implementation changes require a matching PLAN.md update. "
            f"Changed implementation files: {', '.join(sorted(implementation_files))}"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--plan-path", type=Path, default=Path("PLAN.md"))
    args = parser.parse_args()
    violations = verify_guardrails(args.base_ref, args.head_ref, args.plan_path)
    if violations:
        for violation in violations:
            print(violation)
        return 1
    print("Agentic guardrails verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
