import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AgenticConfigurationTests(unittest.TestCase):
    def test_mcp_configs_expose_the_same_servers(self):
        antigravity = json.loads((REPO_ROOT / ".agents" / "mcp_config.json").read_text(encoding="utf-8"))
        vscode = json.loads((REPO_ROOT / ".vscode" / "mcp.json").read_text(encoding="utf-8"))

        self.assertEqual(
            set(antigravity["mcpServers"]),
            set(vscode["mcp"]["servers"]),
        )
        self.assertEqual(
            antigravity["mcpServers"]["fetch"],
            vscode["mcp"]["servers"]["fetch"],
        )

    def test_copilot_setup_workflow_has_required_environment_steps(self):
        workflow = (REPO_ROOT / ".github" / "workflows" / "copilot-setup-steps.yml").read_text(
            encoding="utf-8"
        )

        for required_text in (
            "workflow_dispatch:",
            "copilot-setup-steps:",
            'python-version: "3.14"',
            "python -m pip install -e .",
            "contents: read",
        ):
            with self.subTest(required_text=required_text):
                self.assertIn(required_text, workflow)

    def test_copilot_instructions_delegate_shared_rules(self):
        instructions = (REPO_ROOT / ".github" / "copilot-instructions.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("AGENTS.md", instructions)
        self.assertIn("nflcompanion` and `fetch` MCP servers", instructions)
        self.assertNotIn("## Draft strategy creation", instructions)
        self.assertNotIn("## GitHub issue-driven feature workflow", instructions)


if __name__ == "__main__":
    unittest.main()
