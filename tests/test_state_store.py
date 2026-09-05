import json
import tempfile
import unittest
from pathlib import Path

from nflcompanion.state_store import (
    SUPPORTED_DRAFT_STYLES,
    load_players,
    query_players,
    save_draft_strategy,
    strategies_for_session,
)


class StateStoreTests(unittest.TestCase):
    def test_load_and_query_normalizes_provider_key(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "players.json"
            snapshot.write_text(json.dumps({"123": {
                "full_name": "Test Receiver", "player_id": None,
                "position": "WR", "fantasy_positions": ["WR"],
                "team": "TST", "active": True,
            }}), encoding="utf-8")
            result = query_players(load_players(snapshot), position="wr", active_only=True)
            self.assertEqual(result[0]["provider_id"], "123")

    def test_query_filters_name_and_team(self):
        players = [
            {"provider_id": "1", "full_name": "Alpha Runner",
             "fantasy_positions": ["RB"], "team": "AAA", "active": True},
            {"provider_id": "2", "full_name": "Beta Runner",
             "fantasy_positions": ["RB"], "team": "BBB", "active": True},
        ]
        self.assertEqual(
            [player["provider_id"] for player in query_players(players, name="alpha", team="aaa")],
            ["1"],
        )

    def test_save_and_load_multiple_strategies_for_league_season(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            first = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Hero RB",
                strategy={"priorities": ["RB", "WR"]},
            )
            second = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Zero RB",
                strategy={"priorities": ["WR", "TE"]},
            )
            session = strategies_for_session(state_root, league_id="league-1", season=2026)
            self.assertEqual(first["strategy_id"], "league-1-2026-1")
            self.assertEqual(second["strategy_id"], "league-1-2026-2")
            self.assertEqual(session["session"]["draft_style"], "sleeper_dynasty")
            self.assertEqual([s["name"] for s in session["strategies"]], ["Hero RB", "Zero RB"])

    def test_league_and_season_strategies_are_isolated(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="espn_snake",
                reverse_round=True,
                name="Balanced",
                strategy={"priorities": ["RB", "WR"]},
            )
            save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2027,
                draft_style="espn_snake",
                reverse_round=False,
                name="Anchor WR",
                strategy={"priorities": ["WR", "RB"]},
            )
            save_draft_strategy(
                state_root,
                league_id="league-2",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Prospects",
                strategy={"priorities": ["WR", "QB"]},
            )
            first = strategies_for_session(state_root, league_id="league-1", season=2026)
            second = strategies_for_session(state_root, league_id="league-1", season=2027)
            third = strategies_for_session(state_root, league_id="league-2", season=2026)
            self.assertTrue(first["session"]["reverse_round"])
            self.assertFalse(second["session"]["reverse_round"])
            self.assertEqual(first["strategies"][0]["name"], "Balanced")
            self.assertEqual(second["strategies"][0]["name"], "Anchor WR")
            self.assertEqual(third["strategies"][0]["name"], "Prospects")

    def test_reverse_round_allowed_only_for_espn_snake(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            self.assertIn("sleeper_dynasty", SUPPORTED_DRAFT_STYLES)
            self.assertIn("espn_snake", SUPPORTED_DRAFT_STYLES)
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    reverse_round=True,
                    name="Invalid",
                    strategy={"priorities": ["RB"]},
                )
