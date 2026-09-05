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
            self.assertEqual(payload["agent_workflow"]["orchestrator"]["role"], "orchestrator")
            self.assertEqual(payload["agent_workflow"]["orchestrator"]["prompt_file"], "docs/draft-strategy-agents/orchestrator.md")

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
            self.assertEqual(payload["agent_workflow"]["pattern"], "orchestrated_sequential_pipeline")
            self.assertEqual(
                payload["agent_workflow"]["human_gate"],
                "user_confirmation_before_persistence",
            )
            self.assertIn("short_term", payload["agent_workflow"]["memory"])
            self.assertIn("output", payload["agent_workflow"]["handoff_contract"])
            self.assertTrue(payload["agent_workflow"]["quality_gates"])
            strategy_agents = {
                item["agent"]
                for item in payload["agent_workflow"]["agents"]
                if item["role"] == "strategy_agent"
            }
            self.assertEqual(strategy_agents, {"espn-snake-strategy-agent"})
            self.assertTrue(
                any(
                    item["prompt_file"] == "docs/draft-strategy-agents/espn-strategy-agent.md"
                    for item in payload["agent_workflow"]["agents"]
                )
            )
            self.assertTrue(
                any(
                    item["role"] == "evaluator"
                    and item["prompt_file"] == "docs/draft-strategy-agents/evaluator.md"
                    for item in payload["agent_workflow"]["agents"]
                )
            )
            self.assertTrue((state_root.parent / payload["draft_context_file"]).exists())

    def test_completed_espn_sessions_create_distinct_strategy_files(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            strategy_json = json.dumps(
                {
                    "summary": "Anchor RB, then add WR volume.",
                    "anchor_position": "RB",
                    "second_round_plan": "Pair the RB with a top WR.",
                    "quarterback_plan": "Wait for a middle tier.",
                    "tight_end_plan": "Take an elite TE only at value.",
                    "priority_positions": ["RB", "WR", "QB"],
                    "avoid_early": ["K", "DST"],
                    "round_plan": [{"rounds": "1-3", "targets": ["RB", "WR", "RB"]}],
                    "roster_target": {"QB": 2, "RB": 5, "WR": 4, "TE": 1, "DEF": 1, "K": 1},
                }
            )
            common_arguments = (
                "--state-root",
                str(state_root),
                "--league-id",
                "league-1",
                "--season",
                "2026",
                "--draft-style",
                "espn_snake",
                "--name",
                "RB Anchor Session",
                "--strategy-json",
                strategy_json,
            )
            first = self.run_script(*common_arguments)
            second = self.run_script(*common_arguments)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_payload = json.loads(first.stdout)
            second_payload = json.loads(second.stdout)
            self.assertNotEqual(first_payload["strategy_id"], second_payload["strategy_id"])
            self.assertNotEqual(first_payload["draft_context_file"], second_payload["draft_context_file"])
            self.assertTrue((state_root.parent / first_payload["draft_context_file"]).exists())
            self.assertTrue((state_root.parent / second_payload["draft_context_file"]).exists())

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
