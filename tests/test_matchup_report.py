import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import suggest_starters
from nflcompanion.matchup_report import (
    build_projection_comparison,
    get_matchup_projections,
)


class TestMatchupProjectionReport(unittest.TestCase):
    def setUp(self):
        self.players = {
            "1": {"player_id": "1", "full_name": "Player One", "position": "QB", "team": "BUF"},
            "2": {"player_id": "2", "full_name": "Player Two", "position": "RB", "team": "KC"},
            "3": {"player_id": "3", "full_name": "Player Three", "position": "WR", "team": "NYG"},
        }

    def test_comparison_reports_totals_and_projected_edge(self):
        report = build_projection_comparison(
            ["1", "2"],
            ["3"],
            self.players,
            {"1": 20.2, "2": 10, "3": 14},
            platform="sleeper",
        )
        report_text = "\n".join(report)

        self.assertIn("- **Your projected total:** 30.2 pts (2/2 starters projected)", report_text)
        self.assertIn("- **Opponent projected total:** 14.0 pts (1/1 starters projected)", report_text)
        self.assertIn("- **Projected edge:** Your team by 16.2 pts.", report_text)
        self.assertIn("**Player One** (QB - BUF) - 20.2 projected pts", report_text)
        self.assertIn("**Player Three** (WR - NYG) - 14.0 projected pts", report_text)

    def test_missing_and_invalid_projections_are_excluded(self):
        report = build_projection_comparison(
            ["1", "2"],
            ["3"],
            self.players,
            {"1": 20, "2": float("nan")},
            platform="sleeper",
        )
        report_text = "\n".join(report)

        self.assertIn("20.0 pts partial subtotal (1/2 starters projected)", report_text)
        self.assertIn("projection unavailable", report_text)
        self.assertIn(
            "- **Projected edge:** unavailable: missing projections for 2 starters.",
            report_text,
        )

    def test_espn_projections_are_mapped_to_snapshot_ids(self):
        provider = MagicMock()
        provider.get_projections.return_value = {}
        matchup_data = {
            "user": {"player_projected": {"espn-1": 12.5}},
            "opponent": {"player_projected": {"espn-2": 9}},
        }

        projections = get_matchup_projections(
            provider,
            8,
            "espn",
            matchup_data,
            {"espn-1": "1", "espn-2": "2"},
        )

        self.assertEqual(projections, {"1": 12.5, "2": 9})
        provider.get_projections.assert_called_once_with(8)

    @patch("suggest_starters.load_players")
    @patch("suggest_starters.fetch_sleeper_players.save_snapshot")
    @patch("suggest_starters.fetch_sleeper_players.fetch_players")
    @patch("suggest_starters.get_provider")
    @patch("suggest_starters.load_config")
    def test_scheduled_matchup_report_includes_projection_comparison(
        self,
        mock_load_config,
        mock_get_provider,
        mock_fetch_players,
        mock_save_snapshot,
        mock_load_players,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = MagicMock()
            provider.get_user_matchup.return_value = {
                "user": {"starters": ["1"], "players": ["1", "2"]},
                "opponent": {"starters": ["3"], "players": ["3"]},
            }
            provider.get_projections.return_value = {"1": 22.0, "3": 17.5}
            provider.get_player_fallback_metadata.return_value = {}
            mock_load_config.return_value = {
                "dynasty_league_id": "league",
                "sleeper_user_id": "user",
            }
            mock_get_provider.return_value = provider
            mock_fetch_players.return_value = {}
            mock_save_snapshot.return_value = Path(temp_dir) / "snapshot.json"
            mock_load_players.return_value = list(self.players.values())

            with patch("sys.argv", ["suggest_starters.py", "--workspace", temp_dir, "--week", "8"]):
                result = suggest_starters.main()

            report = (Path(temp_dir) / "weekly_matchup_suggestion.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(result, 0)
            self.assertIn("# Week 8 Dynasty Matchup Suggestion", report)
            self.assertIn("- **Your projected total:** 22.0 pts (1/1 starters projected)", report)
            self.assertIn("- **Opponent projected total:** 17.5 pts (1/1 starters projected)", report)
            self.assertIn("- **Projected edge:** Your team by 4.5 pts.", report)

    @patch("suggest_starters.get_provider")
    @patch("suggest_starters.load_config")
    def test_scheduled_report_handles_missing_opponent(
        self, mock_load_config, mock_get_provider
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = MagicMock()
            provider.get_user_matchup.return_value = {
                "user": {"starters": ["1"]},
                "opponent": None,
            }
            mock_load_config.return_value = {
                "dynasty_league_id": "league",
                "sleeper_user_id": "user",
            }
            mock_get_provider.return_value = provider

            with patch("sys.argv", ["suggest_starters.py", "--workspace", temp_dir, "--week", "8"]):
                result = suggest_starters.main()

            report = (Path(temp_dir) / "weekly_matchup_suggestion.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(result, 0)
            self.assertIn("No opponent found for week 8. (Bye week?)", report)
            self.assertIn("Comparison unavailable because no opponent matchup was found.", report)
            provider.get_projections.assert_not_called()


if __name__ == "__main__":
    unittest.main()
