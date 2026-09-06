"""Unit tests for the nflcompanion MCP server."""

import io
import json
import tempfile
import unittest
from pathlib import Path

from nflcompanion.mcp_server import (
    TOOLS,
    handle_message,
    run_stdio_server,
)


class MCPServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_root = Path(self.temp_dir.name)

        # Create dummy player snapshot
        players_raw = self.state_root / "players" / "raw"
        players_raw.mkdir(parents=True, exist_ok=True)
        player_data = {
            "4034": {
                "player_id": "4034",
                "full_name": "Saquon Barkley",
                "position": "RB",
                "fantasy_positions": ["RB"],
                "team": "PHI",
                "active": True,
            },
            "4035": {
                "player_id": "4035",
                "full_name": "Justin Jefferson",
                "position": "WR",
                "fantasy_positions": ["WR"],
                "team": "MIN",
                "active": True,
            },
        }
        (players_raw / "sleeper-players-2026-09-05T120000000Z.json").write_text(
            json.dumps(player_data), encoding="utf-8"
        )

    def test_initialize(self):
        response = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertIsNotNone(response)
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["serverInfo"]["name"], "nflcompanion")

    def test_ping(self):
        response = handle_message({"jsonrpc": "2.0", "id": 2, "method": "ping"})
        self.assertIsNotNone(response)
        self.assertEqual(response["id"], 2)
        self.assertEqual(response["result"], {})

    def test_tools_list(self):
        response = handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
        self.assertIsNotNone(response)
        tool_names = [t["name"] for t in response["result"]["tools"]]
        self.assertIn("sleeper_ensure_player_state", tool_names)
        self.assertIn("sleeper_query_players", tool_names)
        self.assertIn("draft_get_session", tool_names)
        self.assertIn("draft_init_session", tool_names)
        self.assertIn("draft_recommend_candidates", tool_names)
        self.assertIn("draft_record_pick", tool_names)
        self.assertIn("draft_record_observed_pick", tool_names)
        self.assertIn("draft_observe_pick", tool_names)
        self.assertIn("draft_next_pick_preview", tool_names)
        self.assertIn("draft_update_strategy", tool_names)
        self.assertIn("draft_sync_sleeper_picks", tool_names)

    def test_sleeper_query_players_tool(self):
        call_msg = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "sleeper_query_players",
                "arguments": {
                    "state_root": str(self.state_root),
                    "name": "Barkley",
                },
            },
        }
        response = handle_message(call_msg)
        self.assertIsNotNone(response)
        self.assertFalse(response["result"]["isError"])
        content_text = response["result"]["content"][0]["text"]
        data = json.loads(content_text)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["players"][0]["full_name"], "Saquon Barkley")

    def test_draft_session_and_pick_flow(self):
        # Init draft session
        init_call = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "test-league",
                    "season": 2026,
                    "draft_style": "espn_snake",
                    "team_count": 16,
                    "user_slot": 9,
                },
            },
        }
        response = handle_message(init_call)
        self.assertFalse(response["result"]["isError"])

        # Unconfirmed pick should fail
        unconfirmed_call = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "draft_record_pick",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "test-league",
                    "season": 2026,
                    "provider_id": "4034",
                    "full_name": "Saquon Barkley",
                    "confirmed": False,
                },
            },
        }
        response = handle_message(unconfirmed_call)
        self.assertTrue(response["result"]["isError"])
        self.assertIn("explicit confirmation gate", response["result"]["content"][0]["text"])

        # Confirmed pick should succeed
        confirmed_call = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "draft_record_pick",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "test-league",
                    "season": 2026,
                    "provider_id": "4034",
                    "full_name": "Saquon Barkley",
                    "confirmed": True,
                },
            },
        }
        response = handle_message(confirmed_call)
        self.assertFalse(response["result"]["isError"])
        pick_data = json.loads(response["result"]["content"][0]["text"])
        session_data = pick_data["session"]
        self.assertEqual(session_data["status"], "active")
        self.assertEqual(len(session_data["selected_players"]), 1)
        self.assertEqual(session_data["selected_players"][0]["full_name"], "Saquon Barkley")
        self.assertEqual(pick_data["roster_summary"]["position_counts"]["RB"], 1)

    def test_draft_get_session_tool(self):
        handle_message({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "get-league",
                    "season": 2026,
                    "draft_style": "espn_snake",
                    "team_count": 16,
                    "user_slot": 9,
                },
            },
        })
        response = handle_message({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "draft_get_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "get-league",
                    "season": 2026,
                },
            },
        })
        self.assertFalse(response["result"]["isError"])
        data = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(data["session"]["league_id"], "get-league")
        self.assertEqual(data["next_pick"]["overall_pick"], 9)
        self.assertIn("roster_summary", data)

    def test_draft_init_session_allow_existing(self):
        args = {
            "state_root": str(self.state_root),
            "league_id": "idempotent-league",
            "season": 2026,
            "draft_style": "espn_snake",
            "team_count": 16,
            "user_slot": 9,
        }
        res1 = handle_message({"jsonrpc": "2.0", "id": 12, "method": "tools/call", "params": {"name": "draft_init_session", "arguments": args}})
        self.assertFalse(res1["result"]["isError"])

        res2 = handle_message({"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {"name": "draft_init_session", "arguments": {**args, "allow_existing": True}}})
        self.assertFalse(res2["result"]["isError"])
        data = json.loads(res2["result"]["content"][0]["text"])
        self.assertTrue(data.get("already_existed"))

    def test_draft_observed_pick_and_recommendation_exclusion(self):
        # Init session
        handle_message({
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "obs-league",
                    "season": 2026,
                    "draft_style": "espn_snake",
                    "team_count": 16,
                    "user_slot": 9,
                },
            },
        })
        # Record opponent pick for Jefferson using draft_record_observed_pick with auto-resolution
        obs_res = handle_message({
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "draft_record_observed_pick",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "obs-league",
                    "season": 2026,
                    "overall_pick": 1,
                    "full_name": "Justin Jefferson",
                },
            },
        })
        self.assertFalse(obs_res["result"]["isError"])
        obs_data = json.loads(obs_res["result"]["content"][0]["text"])
        self.assertEqual(obs_data["current_overall_pick"], 1)
        self.assertEqual(obs_data["observed_picks_count"], 1)

        # Recommend candidates with Barkley and Jefferson: Jefferson must be filtered out!
        rec_res = handle_message({
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "draft_recommend_candidates",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "obs-league",
                    "season": 2026,
                    "candidates": ["Barkley", "Jefferson"],
                },
            },
        })
        self.assertFalse(rec_res["result"]["isError"])
        rec_data = json.loads(rec_res["result"]["content"][0]["text"])
        recommended_names = [r["full_name"] for r in rec_data["recommendations"]]
        self.assertIn("Saquon Barkley", recommended_names)
        self.assertNotIn("Justin Jefferson", recommended_names)
        self.assertIn("roster_summary", rec_data)

    def test_draft_record_pick_with_auto_resolution(self):
        handle_message({
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "autores-league",
                    "season": 2026,
                    "draft_style": "espn_snake",
                    "team_count": 16,
                    "user_slot": 1,
                },
            },
        })
        # Record pick passing only full_name and confirmed
        res = handle_message({
            "jsonrpc": "2.0",
            "id": 18,
            "method": "tools/call",
            "params": {
                "name": "draft_record_pick",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "autores-league",
                    "season": 2026,
                    "full_name": "Saquon Barkley",
                    "confirmed": True,
                },
            },
        })
        self.assertFalse(res["result"]["isError"])
        data = json.loads(res["result"]["content"][0]["text"])
        player = data["session"]["selected_players"][0]
        self.assertEqual(player["provider_id"], "4034")
        self.assertEqual(player["position"], "RB")
        self.assertEqual(player["team"], "PHI")

    def test_draft_update_strategy_and_preview(self):
        handle_message({
            "jsonrpc": "2.0",
            "id": 19,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "strat-league",
                    "season": 2026,
                    "draft_style": "espn_snake",
                    "team_count": 16,
                    "user_slot": 1,
                },
            },
        })
        update_res = handle_message({
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "draft_update_strategy",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "strat-league",
                    "season": 2026,
                    "priority_positions": ["WR", "TE"],
                    "notes": "Target TE early",
                },
            },
        })
        self.assertFalse(update_res["result"]["isError"])
        strat = json.loads(update_res["result"]["content"][0]["text"])
        self.assertEqual(strat["priority_positions"], ["WR", "TE"])

        prev_res = handle_message({
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "draft_next_pick_preview",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "strat-league",
                    "season": 2026,
                },
            },
        })
        self.assertFalse(prev_res["result"]["isError"])
        prev_data = json.loads(prev_res["result"]["content"][0]["text"])
        self.assertEqual(prev_data["recommended_positions"], ["WR", "TE"])
    def test_draft_record_pick_defaults_to_confirmed(self):
        # Initializing session
        handle_message({
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "auto-confirmed-league",
                    "season": 2026,
                    "draft_style": "sleeper_dynasty",
                    "team_count": 10,
                    "user_slot": 1,
                },
            },
        })

        # Calling draft_record_pick without confirmed argument should succeed by default
        pick_call = {
            "jsonrpc": "2.0",
            "id": 51,
            "method": "tools/call",
            "params": {
                "name": "draft_record_pick",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "auto-confirmed-league",
                    "season": 2026,
                    "full_name": "Saquon Barkley",
                },
            },
        }
        response = handle_message(pick_call)
        self.assertFalse(response["result"]["isError"])
        pick_data = json.loads(response["result"]["content"][0]["text"])
        self.assertEqual(len(pick_data["session"]["selected_players"]), 1)
        self.assertEqual(pick_data["session"]["selected_players"][0]["full_name"], "Saquon Barkley")

    def test_draft_recommend_auto_syncs_sleeper_picks(self):
        # Create session with draft_id
        handle_message({
            "jsonrpc": "2.0",
            "id": 60,
            "method": "tools/call",
            "params": {
                "name": "draft_init_session",
                "arguments": {
                    "state_root": str(self.state_root),
                    "league_id": "autosync-league",
                    "season": 2026,
                    "draft_style": "sleeper_dynasty",
                    "team_count": 10,
                    "user_slot": 8,
                    "draft_id": "mock-draft-123",
                },
            },
        })

        # Mock sync_sleeper_draft_picks to record Saquon Barkley as an opponent pick
        with unittest.mock.patch("nflcompanion.mcp_server.sync_sleeper_draft_picks") as mock_sync:
            def fake_sync(state_root, **kwargs):
                from nflcompanion.draft_companion import record_observed_pick
                record_observed_pick(
                    state_root,
                    league_id="autosync-league",
                    season=2026,
                    provider_id="4034",
                    player={"full_name": "Saquon Barkley", "position": "RB", "team": "PHI"},
                    overall_pick=1,
                )
                return {}
            mock_sync.side_effect = fake_sync

            rec_call = {
                "jsonrpc": "2.0",
                "id": 61,
                "method": "tools/call",
                "params": {
                    "name": "draft_recommend_candidates",
                    "arguments": {
                        "state_root": str(self.state_root),
                        "league_id": "autosync-league",
                        "season": 2026,
                        "candidates": ["Saquon Barkley", "Justin Jefferson"],
                    },
                },
            }
            response = handle_message(rec_call)
            self.assertFalse(response["result"]["isError"])
            mock_sync.assert_called_once()
            data = json.loads(response["result"]["content"][0]["text"])
            # Saquon was drafted by opponent during sync, so only Jefferson is recommended
            rec_names = [r["full_name"] for r in data["recommendations"]]
            self.assertIn("Justin Jefferson", rec_names)
            self.assertNotIn("Saquon Barkley", rec_names)

    def test_run_stdio_server(self):
        input_stream = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
        )
        output_stream = io.StringIO()
        run_stdio_server(stdin=input_stream, stdout=output_stream)
        output_lines = [line for line in output_stream.getvalue().splitlines() if line]
        self.assertEqual(len(output_lines), 1)
        response = json.loads(output_lines[0])
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"], {})


if __name__ == "__main__":
    unittest.main()

