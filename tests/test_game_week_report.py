import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add scripts to path to import game_week_report
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import game_week_report

class TestGameWeekReport(unittest.TestCase):
    def setUp(self):
        self.mock_provider = MagicMock()
        self.all_players = {
            "1": {"full_name": "Tom Brady", "position": "QB", "team": "TB", "injury_status": ""},
            "2": {"full_name": "Julio Jones", "position": "WR", "team": "ATL", "injury_status": "Out"},
            "3": {"full_name": "Bench Player", "position": "QB", "team": "BUF", "injury_status": ""},
            "4": {"full_name": "Opponent Star", "position": "RB", "team": "TEN", "injury_status": ""},
        }
        self.espn_to_sleeper = {}
        self.workspace = Path("/tmp/mock_workspace")

    def test_analyze_previous_week_sleeper(self):
        # Mock matchup data
        self.mock_provider.get_user_matchup.return_value = {
            "user": {
                "starters": ["1", "2"],
                "players": ["1", "2", "3"],
                "points": 35.5,
                "starters_points": [25.0, 0.0],
                "players_points": {"1": 25.0, "2": 0.0, "3": 30.0}
            },
            "opponent": {}
        }
        
        # Mock projections
        self.mock_provider.get_projections.return_value = {
            "1": 20.0,
            "2": 15.0,
            "3": 10.0
        }
        
        report = game_week_report.analyze_previous_week(
            self.mock_provider, "sleeper", "league1", "user1", 1, self.all_players, self.espn_to_sleeper
        )
        
        report_text = "\n".join(report)
        self.assertIn("- **Total Points:** 35.50 (Projected: 35.00 | Diff: +0.50)", report_text)
        self.assertIn("- **Top Scorer:** Tom Brady with 25.00 pts", report_text)
        self.assertIn("- **Worst Scorer:** Julio Jones with 0.00 pts", report_text)
        self.assertIn("- **Bench Hindsight:** Bench Player (30.00 pts) outscored Tom Brady (25.00 pts).", report_text)

    @patch("fetch_sleeper_trending.fetch_trending")
    @patch("game_week_report.latest_trending_snapshot")
    def test_analyze_next_week_sleeper(self, mock_latest, mock_fetch):
        # Mock matchup
        self.mock_provider.get_user_matchup.return_value = {
            "user": {
                "starters": ["1", "2"],
                "players": ["1", "2", "3"]
            },
            "opponent": {
                "starters": ["4"],
                "players": ["4"]
            }
        }
        
        self.mock_provider.get_all_rostered_players.return_value = {"1", "2", "3", "4"}
        
        # We will make fetch_trending fail to test fallback or just let it return []
        mock_fetch.side_effect = Exception("API error")
        mock_latest.return_value = None # No snapshot either
        
        # Monkey patch NFL_BYE_WEEKS_2026 just for the test
        original_byes = game_week_report.NFL_BYE_WEEKS_2026.copy()
        game_week_report.NFL_BYE_WEEKS_2026["TB"] = 2
        
        try:
            report = game_week_report.analyze_next_week(
                self.mock_provider, "sleeper", "league1", "user1", 2, self.all_players, self.espn_to_sleeper, self.workspace
            )
            
            report_text = "\n".join(report)
            
            # Check for byes and injuries
            self.assertIn("**Tom Brady** (QB - TB): BYE WEEK", report_text)
            self.assertIn("**Julio Jones** (WR - ATL): Injury: Out", report_text)
            
            # Bench alternative
            self.assertIn("**Bench Player** (QB - BUF) - Healthy", report_text)
            
            # Opponent
            self.assertIn("**Opponent Star** (RB - TEN)", report_text)
            
            # Waivers empty fallback
            self.assertIn("- No obvious trending free agents found.", report_text)
        finally:
            game_week_report.NFL_BYE_WEEKS_2026.clear()
            game_week_report.NFL_BYE_WEEKS_2026.update(original_byes)

    @patch("fetch_sleeper_trending.fetch_trending")
    @patch("game_week_report.latest_trending_snapshot")
    def test_analyze_next_week_recommends_keeping_healthy_lineup(self, mock_latest, mock_fetch):
        self.mock_provider.get_user_matchup.return_value = {
            "user": {
                "starters": ["1", "4"],
                "players": ["1", "3", "4"],
            },
            "opponent": {
                "starters": ["2"],
                "players": ["2"],
            },
        }

        self.mock_provider.get_all_rostered_players.return_value = {"1", "2", "3", "4"}
        mock_fetch.side_effect = Exception("API error")
        mock_latest.return_value = None

        report = game_week_report.analyze_next_week(
            self.mock_provider, "sleeper", "league1", "user1", 2, self.all_players, self.espn_to_sleeper, self.workspace
        )

        report_text = "\n".join(report)
        self.assertIn("No immediate red flags (byes/injuries) found among your starters.", report_text)
        self.assertIn("### Start/Sit Recommendations", report_text)
        self.assertIn(
            "- Start your current lineup this week; no bye-week or injury-driven swaps are needed right now.",
            report_text,
        )

if __name__ == "__main__":
    unittest.main()
