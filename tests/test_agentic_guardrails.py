import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "check_agentic_guardrails.py"


class AgenticGuardrailTests(unittest.TestCase):
    def create_repo(self) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        directory = Path(temporary_directory.name)
        subprocess.run(["git", "init"], cwd=directory, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=directory, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=directory, check=True, capture_output=True, text=True)
        (directory / "src").mkdir()
        (directory / "scripts").mkdir()
        (directory / "PLAN.md").write_text("# Plan\n\nStatus: ready\n", encoding="utf-8")
        (directory / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "PLAN.md", "src/module.py"], cwd=directory, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=directory, check=True, capture_output=True, text=True)
        return directory

    def run_guardrail(
        self,
        repo: Path,
        *,
        base_sha: str | None = None,
        diff_mode: str = "range",
    ) -> subprocess.CompletedProcess[str]:
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        if base_sha is None:
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD^"], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()
        import sys
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--base-ref",
                base_sha,
                "--head-ref",
                head_sha,
                "--diff-mode",
                diff_mode,
            ],
            cwd=repo,
            capture_output=True,
            text=True,
        )

    def test_rejects_implementation_change_without_plan_update(self):
        repo = self.create_repo()
        (repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "code only"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Implementation changes require a matching PLAN.md update", result.stdout)

    def test_allows_implementation_change_with_plan_update(self):
        repo = self.create_repo()
        (repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        (repo / "PLAN.md").write_text("# Plan\n\nStatus: updated\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "code and plan"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Agentic guardrails verified.", result.stdout)

    def test_allows_exempt_guardrail_script_change_without_plan_update(self):
        repo = self.create_repo()
        (repo / "scripts" / "check_agentic_guardrails.py").write_text("print('guardrail')\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "scripts/check_agentic_guardrails.py"],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "commit", "-m", "guardrail only"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Agentic guardrails verified.", result.stdout)

    def test_rejects_missing_plan_artifact(self):
        repo = self.create_repo()
        subprocess.run(["git", "rm", "PLAN.md"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "remove plan"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing required plan artifact", result.stdout)

    def test_rejects_plan_without_status_line(self):
        repo = self.create_repo()
        (repo / "PLAN.md").write_text("# Plan\n\nNo Status: line here.\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "bad plan"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must include a Status line", result.stdout)

    def test_zero_sha_base_still_checks_latest_commit(self):
        repo = self.create_repo()
        (repo / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "code only"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo, base_sha="0" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Implementation changes require a matching PLAN.md update", result.stdout)

    def test_merge_base_diff_ignores_base_branch_only_changes(self):
        repo = self.create_repo()
        initial_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "checkout", "-b", "base-branch", initial_sha], cwd=repo, check=True, capture_output=True, text=True)
        (repo / "src" / "module.py").write_text("VALUE = 3\n", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "base branch code"], cwd=repo, check=True, capture_output=True, text=True)
        base_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "checkout", "feature"], cwd=repo, check=True, capture_output=True, text=True)
        (repo / "docs.txt").write_text("notes\n", encoding="utf-8")
        subprocess.run(["git", "add", "docs.txt"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "feature docs"], cwd=repo, check=True, capture_output=True, text=True)
        result = self.run_guardrail(repo, base_sha=base_sha, diff_mode="merge-base")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Agentic guardrails verified.", result.stdout)
