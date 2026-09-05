import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "create_draft_strategy.py"


class CreateDraftStrategyScriptTests(unittest.TestCase):
    def run_script(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT_PATH), *arguments],
            cwd=SCRIPT_PATH.parent.parent,
            capture_output=True,
            text=True,
        )

    def test_simulate_writes_strategy_to_draft_context(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "sleeper_dynasty",
                "--simulate",
                "--seed",
                "1",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["creation_mode"], "simulation")
            self.assertTrue((state_root.parent / payload["draft_context_file"]).exists())

    def test_interactive_flow_requires_valid_strategy_json(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "sleeper_dynasty",
                "--name",
                "Broken",
                "--strategy-json",
                "{bad json}",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--strategy-json must be valid JSON", result.stderr)

    def test_interactive_flow_saves_strategy_and_questionnaire(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "espn_snake",
                "--reverse-round",
                "--name",
                "Interactive WR Anchor",
                "--strategy-json",
                json.dumps(
                    {
                        "summary": "Prioritize stable WR volume early.",
                        "priority_positions": ["WR", "RB"],
                        "avoid_early": ["K", "DST"],
                        "round_plan": [{"rounds": "1-3", "targets": ["WR", "WR", "RB"]}],
                    }
                ),
                "--questionnaire-json",
                json.dumps([{"question": "Start", "answer": "WR"}]),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["name"], "Interactive WR Anchor")
            self.assertEqual(payload["questionnaire"][0]["answer"], "WR")
            self.assertTrue((state_root.parent / payload["draft_context_file"]).exists())

    def test_interactive_flow_rejects_malformed_questionnaire_items(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "sleeper_dynasty",
                "--name",
                "Broken questionnaire",
                "--strategy-json",
                json.dumps(
                    {
                        "priority_positions": ["WR", "RB"],
                        "avoid_early": ["K", "DST"],
                        "round_plan": [{"rounds": "1-3", "targets": ["WR", "WR", "RB"]}],
                    }
                ),
                "--questionnaire-json",
                json.dumps(["just text"]),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--questionnaire-json item 0 must be an object", result.stderr)

    def test_interactive_flow_rejects_non_string_validation_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "sleeper_dynasty",
                "--name",
                "Broken feedback",
                "--strategy-json",
                json.dumps(
                    {
                        "priority_positions": ["WR", "RB"],
                        "avoid_early": ["K", "DST"],
                        "round_plan": [{"rounds": "1-3", "targets": ["WR", "WR", "RB"]}],
                    }
                ),
                "--validation-feedback-json",
                json.dumps(["good", 2]),
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--validation-feedback-json item 1 must be a string", result.stderr)

    def test_sleeper_reverse_round_flag_is_rejected_by_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "sleeper_dynasty",
                "--simulate",
                "--reverse-round",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--reverse-round is only supported for espn_snake", result.stderr)

    def test_espn_simulation_supports_both_reverse_round_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            default_result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "espn_snake",
                "--simulate",
            )
            reverse_round_result = self.run_script(
                "--state-root",
                str(state_root),
                "--league-id",
                "league-2",
                "--season",
                "2026",
                "--draft-style",
                "espn_snake",
                "--simulate",
                "--reverse-round",
            )
            self.assertEqual(default_result.returncode, 0, default_result.stderr)
            self.assertEqual(reverse_round_result.returncode, 0, reverse_round_result.stderr)
            self.assertEqual(json.loads(default_result.stdout)["name"], "Hero RB with Late QB")
            self.assertEqual(json.loads(reverse_round_result.stdout)["name"], "Third-Round Reversal WR Anchor")
