"""Tests for real-time Sleeper draft pick synchronization and batch observed picks."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from nflcompanion.draft_companion import (
    batch_record_observed_picks,
    create_draft_session,
    load_draft_session,
    recommend_candidates,
)
from nflcompanion.sleeper_sync import (
    fetch_sleeper_draft_picks,
    fetch_sleeper_draft_status,
    sync_sleeper_draft_picks,
)


class SleeperSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temp_dir.name)
        self.league_id = "test-sleeper-dynasty-sync"
        self.season = 2026
        create_draft_session(
            self.state_root,
            league_id=self.league_id,
            season=self.season,
            draft_style="sleeper_dynasty",
            team_count=10,
            user_slot=5,
        )
        self.mock_players = [
            {"provider_id": "4984", "full_name": "Josh Allen", "position": "QB", "team": "BUF", "active": True, "search_rank": 1},
            {"provider_id": "7564", "full_name": "Ja'Marr Chase", "position": "WR", "team": "CIN", "active": True, "search_rank": 2},
            {"provider_id": "9509", "full_name": "Bijan Robinson", "position": "RB", "team": "ATL", "active": True, "search_rank": 3},
            {"provider_id": "4034", "full_name": "Christian McCaffrey", "position": "RB", "team": "SF", "active": True, "search_rank": 4},
            {"provider_id": "8138", "full_name": "James Cook", "position": "RB", "team": "BUF", "active": True, "search_rank": 5},
        ]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_sync_sleeper_draft_picks_with_raw_picks(self) -> None:
        """Verify syncing raw picks records opponent picks and skips user slot."""
        raw_picks = [
            {
                "pick_no": 1,
                "round": 1,
                "draft_slot": 1,
                "player_id": "4984",
                "metadata": {"first_name": "Josh", "last_name": "Allen", "position": "QB", "team": "BUF"},
            },
            {
                "pick_no": 2,
                "round": 1,
                "draft_slot": 2,
                "player_id": "7564",
                "metadata": {"first_name": "Ja'Marr", "last_name": "Chase", "position": "WR", "team": "CIN"},
            },
            {
                "pick_no": 5,
                "round": 1,
                "draft_slot": 5,  # user slot
                "player_id": "9509",
                "metadata": {"first_name": "Bijan", "last_name": "Robinson", "position": "RB", "team": "ATL"},
            },
        ]
        result = sync_sleeper_draft_picks(
            self.state_root,
            league_id=self.league_id,
            season=self.season,
            draft_id="123456789",
            players=self.mock_players,
            raw_picks=raw_picks,
        )

        self.assertEqual(len(result["newly_observed_picks"]), 2)
        self.assertEqual(len(result["user_picks_detected"]), 1)
        self.assertEqual(result["user_picks_detected"][0]["provider_id"], "9509")

        # Verify session state reflects observed picks
        loaded = load_draft_session(self.state_root, league_id=self.league_id, season=self.season)
        observed = loaded["session"]["observed_picks"]
        self.assertEqual(len(observed), 2)
        observed_ids = {p["provider_id"] for p in observed}
        self.assertIn("4984", observed_ids)
        self.assertIn("7564", observed_ids)
        self.assertNotIn("9509", observed_ids)

        # Recommendation should exclude observed picks
        rec_result = recommend_candidates(
            self.mock_players,
            ["Josh Allen", "James Cook"],
            drafted_provider_ids=observed_ids,
        )
        rec_ids = [r["provider_id"] for r in rec_result["recommendations"]]
        self.assertNotIn("4984", rec_ids)
        self.assertIn("8138", rec_ids)

    def test_sync_is_idempotent(self) -> None:
        """Calling sync a second time with same picks should not duplicate entries."""
        raw_picks = [
            {
                "pick_no": 1,
                "round": 1,
                "draft_slot": 1,
                "player_id": "4984",
                "metadata": {"first_name": "Josh", "last_name": "Allen", "position": "QB", "team": "BUF"},
            },
        ]
        res1 = sync_sleeper_draft_picks(
            self.state_root,
            league_id=self.league_id,
            season=self.season,
            draft_id="123456789",
            players=self.mock_players,
            raw_picks=raw_picks,
        )
        self.assertEqual(len(res1["newly_observed_picks"]), 1)

        res2 = sync_sleeper_draft_picks(
            self.state_root,
            league_id=self.league_id,
            season=self.season,
            draft_id="123456789",
            players=self.mock_players,
            raw_picks=raw_picks,
        )
        self.assertEqual(len(res2["newly_observed_picks"]), 0)

        loaded = load_draft_session(self.state_root, league_id=self.league_id, season=self.season)
        self.assertEqual(len(loaded["session"]["observed_picks"]), 1)

    def test_batch_record_observed_picks(self) -> None:
        """Verify atomic batch recording of multiple observed opponent picks."""
        picks = [
            {"provider_id": "4984", "overall_pick": 1},
            {"provider_id": "7564", "overall_pick": 2},
        ]
        session = batch_record_observed_picks(
            self.state_root,
            league_id=self.league_id,
            season=self.season,
            picks=picks,
            all_players=self.mock_players,
        )
        self.assertEqual(len(session["observed_picks"]), 2)
        self.assertEqual(session["current_overall_pick"], 2)
        self.assertEqual(session["observed_picks"][0]["full_name"], "Josh Allen")
        self.assertEqual(session["observed_picks"][1]["full_name"], "Ja'Marr Chase")


if __name__ == "__main__":
    unittest.main()
