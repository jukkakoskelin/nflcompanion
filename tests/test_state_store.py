import json
import tempfile
import unittest
from pathlib import Path

from nflcompanion.state_store import load_players, query_players


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
