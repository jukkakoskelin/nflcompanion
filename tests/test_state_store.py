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
            self.assertEqual(first["strategy_id"], "strategy-1")
            self.assertEqual(second["strategy_id"], "strategy-2")
            self.assertIn("created_at", first)
            self.assertIn("created_at", second)
            self.assertEqual(session["session"]["draft_style"], "sleeper_dynasty")
            self.assertEqual([s["name"] for s in session["strategies"]], ["Hero RB", "Zero RB"])
            self.assertIn("created_at", session["strategies"][0])

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

    def test_strategy_id_sequence_does_not_reuse_existing_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": False,
                                    },
                                    "strategies": [
                                        {"strategy_id": "strategy-1", "strategy_number": 1, "name": "First", "strategy": {}},
                                        {"strategy_id": "strategy-3", "strategy_number": 3, "name": "Third", "strategy": {}},
                                    ],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            saved = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Next",
                strategy={"priorities": ["WR"]},
            )
            self.assertEqual(saved["strategy_id"], "strategy-4")
            self.assertEqual(saved["strategy_number"], 4)

    def test_strategies_for_session_returns_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Original",
                strategy={"priorities": ["RB"]},
            )
            view = strategies_for_session(state_root, league_id="league-1", season=2026)
            view["session"]["draft_style"] = "espn_snake"
            view["strategies"][0]["name"] = "Mutated"
            reloaded = strategies_for_session(state_root, league_id="league-1", season=2026)
            self.assertEqual(reloaded["session"]["draft_style"], "sleeper_dynasty")
            self.assertEqual(reloaded["strategies"][0]["name"], "Original")

    def test_save_rejects_inconsistent_existing_session_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "espn",
                                        "draft_type": "snake",
                                        "reverse_round": False,
                                    },
                                    "strategies": [],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                )

    def test_strategies_for_missing_session_returns_empty_result(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            result = strategies_for_session(state_root, league_id="unknown", season=2026)
            self.assertIsNone(result["session"])
            self.assertEqual(result["strategies"], [])

    def test_save_rejects_stored_reverse_round_for_unsupported_style(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": True,
                                    },
                                    "strategies": [],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                    reverse_round=True,
                )

    def test_save_rejects_malformed_league_or_season_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps({"leagues": {"league-1": "invalid"}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                )

            strategy_file.write_text(
                json.dumps({"leagues": {"league-1": {"2026": "invalid"}}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                )

    def test_save_rejects_malformed_strategies_container(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": False,
                                    },
                                    "strategies": {},
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                )

            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": False,
                                    },
                                    "strategies": ["invalid"],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                )

    def test_strategies_for_session_rejects_malformed_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps({"leagues": {"league-1": "invalid"}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                strategies_for_session(state_root, league_id="league-1", season=2026)

            strategy_file.write_text(
                json.dumps({"leagues": {"league-1": {"2026": "invalid"}}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                strategies_for_session(state_root, league_id="league-1", season=2026)

            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": False,
                                    },
                                    "strategies": ["invalid"],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                strategies_for_session(state_root, league_id="league-1", season=2026)

    def test_save_returns_copy_of_input_strategy(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy = {"priorities": ["RB"]}
            saved = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Original",
                strategy=strategy,
            )
            strategy["priorities"].append("WR")
            saved["strategy"]["priorities"].append("QB")
            reloaded = strategies_for_session(state_root, league_id="league-1", season=2026)
            self.assertEqual(reloaded["strategies"][0]["strategy"]["priorities"], ["RB"])

    def test_session_identity_must_match_league_and_season_bucket(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-2",
                                        "season": 2027,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": False,
                                    },
                                    "strategies": [],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                save_draft_strategy(
                    state_root,
                    league_id="league-1",
                    season=2026,
                    draft_style="sleeper_dynasty",
                    name="Should fail",
                    strategy={},
                )
            with self.assertRaises(ValueError):
                strategies_for_session(state_root, league_id="league-1", season=2026)

    def test_strategy_sequence_ignores_non_positive_stored_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            strategy_file = state_root / "strategies" / "strategies.json"
            strategy_file.parent.mkdir(parents=True, exist_ok=True)
            strategy_file.write_text(
                json.dumps(
                    {
                        "leagues": {
                            "league-1": {
                                "2026": {
                                    "session": {
                                        "league_id": "league-1",
                                        "season": 2026,
                                        "draft_style": "sleeper_dynasty",
                                        "platform": "sleeper",
                                        "draft_type": "dynasty",
                                        "reverse_round": False,
                                    },
                                    "strategies": [
                                        {"strategy_id": "strategy-2", "strategy_number": 0, "name": "Bad", "strategy": {}},
                                        {"strategy_id": "strategy-3", "strategy_number": -1, "name": "Bad2", "strategy": {}},
                                    ],
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            saved = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="Valid",
                strategy={},
            )
            self.assertEqual(saved["strategy_number"], 4)
