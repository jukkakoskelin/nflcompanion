import json
import tempfile
import unittest
from pathlib import Path

from nflcompanion.draft_companion import (
    calculate_roster_summary,
    confirm_draft_slot,
    create_draft_session,
    load_draft_session,
    next_pick_for_slot,
    next_pick_preview,
    record_observed_pick,
    pick_for_overall,
    record_pick,
    recommend_candidates,
    update_living_strategy,
)


class DraftCompanionTests(unittest.TestCase):
    def players(self):
        return [
            {
                "provider_id": "1",
                "full_name": "Alpha Smith",
                "position": "WR",
                "fantasy_positions": ["WR"],
                "team": "AAA",
                "active": True,
                "search_rank": 10,
            },
            {
                "provider_id": "2",
                "full_name": "Beta Smith",
                "position": "RB",
                "fantasy_positions": ["RB"],
                "team": "BBB",
                "active": True,
                "search_rank": 20,
            },
            {
                "provider_id": "3",
                "full_name": "Gamma Jones",
                "position": "WR",
                "fantasy_positions": ["WR"],
                "team": "CCC",
                "active": True,
                "search_rank": 30,
            },
            {
                "provider_id": "4",
                "full_name": "Delta Allen",
                "position": "TE",
                "fantasy_positions": ["TE"],
                "team": "DDD",
                "active": True,
            },
        ]

    def test_snake_math_handles_normal_and_third_round_reversal(self):
        self.assertEqual(pick_for_overall(1, 4), {"overall_pick": 1, "round": 1, "slot": 1})
        self.assertEqual(pick_for_overall(5, 4), {"overall_pick": 5, "round": 2, "slot": 4})
        self.assertEqual(pick_for_overall(9, 4), {"overall_pick": 9, "round": 3, "slot": 1})
        self.assertEqual(
            pick_for_overall(9, 4, reverse_round=True),
            {"overall_pick": 9, "round": 3, "slot": 4},
        )
        self.assertEqual(
            next_pick_for_slot(1, 4, 1),
            {"overall_pick": 8, "round": 2, "slot": 1},
        )

    def test_resolution_requires_clarification_for_ambiguous_surname(self):
        result = recommend_candidates(
            self.players(),
            ["Smith", "Jones", "Allen"],
            strategy={"priority_positions": ["WR", "RB"]},
        )
        self.assertEqual(len(result["ambiguous"]), 1)
        self.assertEqual(result["ambiguous"][0]["input"], "Smith")
        self.assertEqual([item["full_name"] for item in result["recommendations"]], ["Gamma Jones", "Delta Allen"])

    def test_recommendation_order_is_deterministic_and_uses_strategy(self):
        result = recommend_candidates(
            self.players(),
            ["Allen TE", "Jones", "Alpha Smith"],
            strategy={"priority_positions": ["WR"]},
        )
        self.assertEqual(
            [item["full_name"] for item in result["recommendations"]],
            ["Alpha Smith", "Gamma Jones", "Delta Allen"],
        )
        self.assertIn("factor_scores", result["recommendations"][0])
        self.assertTrue(result["recommendations"][0]["rationale"])

    def test_session_requires_confirmation_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="espn_snake",
                team_count=4,
                user_slot=1,
                active_strategy={"priority_positions": ["WR", "RB"]},
            )
            with self.assertRaises(PermissionError):
                record_pick(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    provider_id="1",
                    player=self.players()[0],
                    confirmed=False,
                )
            recorded = record_pick(
                state_root,
                league_id="league-1",
                season=2026,
                provider_id="1",
                player=self.players()[0],
                confirmed=True,
                idempotency_key="pick-1",
            )
            repeated = record_pick(
                state_root,
                league_id="league-1",
                season=2026,
                provider_id="1",
                player=self.players()[0],
                confirmed=True,
                idempotency_key="pick-1",
            )
            self.assertEqual(recorded, repeated)
            loaded = load_draft_session(state_root, league_id="league-1", season=2026)
            self.assertEqual(loaded["session"]["selected_players"][0]["full_name"], "Alpha Smith")
            self.assertEqual(loaded["living_strategy"]["confirmed_pick_count"], 1)
            events = (state_root / "drafts" / "league-1" / "2026" / "events.md").read_text(encoding="utf-8")
            self.assertEqual(events.count('"event": "pick_confirmed"'), 1)

    def test_session_files_are_human_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                team_count=10,
                user_slot=3,
                active_strategy={"summary": "Prefer stable volume."},
            )
            session_path = state_root / "drafts" / "league-1" / "2026" / "session.md"
            payload = session_path.read_text(encoding="utf-8")
            self.assertIn("# Draft session", payload)
            self.assertIn("decision_window_seconds: 90", payload)
            self.assertTrue((session_path.parent / "living-strategy.md").exists())
            self.assertTrue((session_path.parent / "events.md").exists())

    def test_next_pick_preview_excludes_observed_players_and_uses_trends(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="espn_snake",
                team_count=4,
                user_slot=1,
                active_strategy={"priority_positions": ["WR", "RB"]},
            )
            record_observed_pick(
                state_root,
                league_id="league-1",
                season=2026,
                provider_id="1",
                player=self.players()[0],
                overall_pick=1,
            )
            preview = next_pick_preview(
                state_root,
                league_id="league-1",
                season=2026,
                players=self.players(),
                trending={"add": [{"player_id": "3", "count": 500}], "drop": []},
            )
            self.assertEqual(preview["next_pick"]["overall_pick"], 8)
            self.assertNotIn("1", [item["provider_id"] for item in preview["watch_list"]])
            self.assertEqual(preview["watch_list"][0]["provider_id"], "3")
            self.assertEqual(preview["watch_list"][0]["availability_estimate"], "likely")

    def test_calculate_roster_summary(self):
        roster = [
            {"provider_id": "1", "full_name": "Player 1", "position": "QB"},
            {"provider_id": "2", "full_name": "Player 2", "position": "RB"},
            {"provider_id": "3", "full_name": "Player 3", "position": "WR"},
            {"provider_id": "4", "full_name": "Defense", "position": "DST"},
        ]
        summary = calculate_roster_summary(roster, target_roster_size=14)
        self.assertEqual(summary["total_selected"], 4)
        self.assertEqual(summary["remaining_slots"], 10)
        self.assertEqual(summary["position_counts"]["QB"], 1)
        self.assertEqual(summary["position_counts"]["RB"], 1)
        self.assertEqual(summary["position_counts"]["WR"], 1)
        self.assertEqual(summary["position_counts"]["DEF"], 1)
        self.assertEqual(summary["position_counts"]["TE"], 0)
        self.assertIn("TE", summary["needs"])
        self.assertIn("K", summary["needs"])
        self.assertNotIn("QB", summary["needs"])
        self.assertNotIn("DEF", summary["needs"])

    def test_update_living_strategy(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="espn_snake",
                team_count=4,
                user_slot=1,
                active_strategy={"priority_positions": ["WR", "RB"]},
            )
            updated = update_living_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                priority_positions=["TE", "QB"],
                avoid_early=["K"],
                notes="Shift to TE early",
            )
            self.assertEqual(updated["priority_positions"], ["TE", "QB"])
            self.assertEqual(updated["avoid_early"], ["K"])
            self.assertEqual(updated["notes"], "Shift to TE early")
            loaded = load_draft_session(state_root, league_id="league-1", season=2026)
            self.assertEqual(loaded["living_strategy"]["priority_positions"], ["TE", "QB"])

    def test_record_pick_with_player_auto_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="espn_snake",
                team_count=4,
                user_slot=1,
            )
            recorded = record_pick(
                state_root,
                league_id="league-1",
                season=2026,
                provider_id="1",
                confirmed=True,
                all_players=self.players(),
            )
            self.assertEqual(len(recorded["selected_players"]), 1)
            player = recorded["selected_players"][0]
            self.assertEqual(player["full_name"], "Alpha Smith")
            self.assertEqual(player["position"], "WR")
            self.assertEqual(player["team"], "AAA")

    # ---------------------------------------------------------------------------
    # Dynasty roster summary tests
    # ---------------------------------------------------------------------------

    def test_dynasty_roster_summary_default_target_size_is_25(self):
        """calculate_roster_summary for sleeper_dynasty should default to 25 active slots."""
        summary = calculate_roster_summary([], draft_style="sleeper_dynasty")
        self.assertEqual(summary["target_roster_size"], 25)

    def test_espn_roster_summary_default_target_size_is_14(self):
        """calculate_roster_summary for espn_snake should default to 14 players."""
        summary = calculate_roster_summary([], draft_style="espn_snake")
        self.assertEqual(summary["target_roster_size"], 14)

    def test_dynasty_roster_summary_requires_two_qbs(self):
        """Dynasty roster needs QB×2 for Superflex; one QB is not enough."""
        one_qb = [{"position": "QB"}]
        summary = calculate_roster_summary(one_qb, draft_style="sleeper_dynasty")
        needs_text = " ".join(summary["needs"])
        self.assertIn("QB", needs_text, f"Expected QB need; got needs={summary['needs']}")
        self.assertIn("Superflex", needs_text, f"Expected Superflex label; got needs={summary['needs']}")

    def test_dynasty_roster_summary_no_def_or_k_needed(self):
        """Dynasty roster should NOT flag DEF or K as needs."""
        # No players at all — still should not require DEF or K
        summary = calculate_roster_summary([], draft_style="sleeper_dynasty")
        needs = summary["needs"]
        self.assertNotIn("DEF", needs, f"DEF should not be required in dynasty; needs={needs}")
        self.assertNotIn("K", needs, f"K should not be required in dynasty; needs={needs}")

    def test_dynasty_roster_summary_requires_three_wrs(self):
        """Dynasty requires 3 WR starters, so fewer than 3 should appear in needs."""
        two_wrs = [{"position": "WR"}, {"position": "WR"}]
        summary = calculate_roster_summary(two_wrs, draft_style="sleeper_dynasty")
        needs_text = " ".join(summary["needs"])
        self.assertIn("WR", needs_text, f"Expected WR need; got needs={summary['needs']}")

    def test_espn_roster_summary_requires_def_and_k(self):
        """ESPN roster should flag DEF and K as needs when missing."""
        summary = calculate_roster_summary([], draft_style="espn_snake")
        needs = summary["needs"]
        self.assertIn("DEF", needs, f"DEF should be required in ESPN; needs={needs}")
        self.assertIn("K", needs, f"K should be required in ESPN; needs={needs}")

    def test_roster_summary_custom_target_size_overrides_default(self):
        """Explicit target_roster_size overrides the style default."""
        summary = calculate_roster_summary([], draft_style="sleeper_dynasty", target_roster_size=10)
        self.assertEqual(summary["target_roster_size"], 10)

    # ---------------------------------------------------------------------------
    # TBD draft slot tests
    # ---------------------------------------------------------------------------

    def test_create_session_with_tbd_slot(self):
        """create_draft_session with user_slot=0 should succeed and mark slot as TBD."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            result = create_draft_session(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                draft_style="sleeper_dynasty",
                team_count=10,
                user_slot=0,  # TBD
            )
            session = result["session"]
            self.assertEqual(session["user_slot"], 0)
            self.assertEqual(session["draft_slot_status"], "TBD")

    def test_create_session_with_known_slot_marks_confirmed(self):
        """create_draft_session with a real slot should mark draft_slot_status as confirmed."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            result = create_draft_session(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                draft_style="sleeper_dynasty",
                team_count=10,
                user_slot=5,
            )
            session = result["session"]
            self.assertEqual(session["user_slot"], 5)
            self.assertEqual(session["draft_slot_status"], "confirmed")

    def test_confirm_draft_slot_updates_tbd_session(self):
        """confirm_draft_slot should update a TBD session to the confirmed slot."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                draft_style="sleeper_dynasty",
                team_count=10,
                user_slot=0,
            )
            confirmed = confirm_draft_slot(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                user_slot=3,
            )
            self.assertEqual(confirmed["user_slot"], 3)
            self.assertEqual(confirmed["draft_slot_status"], "confirmed")

    def test_confirm_draft_slot_rejects_already_confirmed(self):
        """confirm_draft_slot should raise ValueError if the slot is already confirmed."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            create_draft_session(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                draft_style="sleeper_dynasty",
                team_count=10,
                user_slot=7,
            )
            with self.assertRaises(ValueError):
                confirm_draft_slot(
                    state_root,
                    league_id="sleeper-10-dynasty-2026",
                    season=2026,
                    user_slot=3,
                )

    def test_create_session_rejects_invalid_nonzero_slot(self):
        """create_draft_session should reject slots outside 1..team_count (but allow 0)."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            with self.assertRaises(ValueError):
                create_draft_session(
                    state_root,
                    league_id="sleeper-10-dynasty-2026",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    team_count=10,
                    user_slot=11,  # out of range
                )


if __name__ == "__main__":
    unittest.main()
