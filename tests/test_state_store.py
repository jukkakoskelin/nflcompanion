import json
import tempfile
import unittest
from pathlib import Path

from nflcompanion.state_store import (
    SUPPORTED_DRAFT_STYLES,
    latest_trending_snapshot,
    load_players,
    load_strategy_creation_log,
    load_trending,
    query_players,
    query_trending_players,
    retire_draft_strategy,
    save_draft_strategy,
    simulate_draft_strategy,
    strategies_for_session,
    validate_draft_strategy,
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

    def test_latest_trending_snapshot_picks_newest_file(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            raw_dir = state_root / "players" / "trending" / "raw"
            raw_dir.mkdir(parents=True)
            older = raw_dir / "sleeper-trending-2026-01-01T000000000Z.json"
            newer = raw_dir / "sleeper-trending-2026-01-02T000000000Z.json"
            older.write_text(json.dumps({"add": [], "drop": []}), encoding="utf-8")
            newer.write_text(json.dumps({"add": [], "drop": []}), encoding="utf-8")
            self.assertEqual(latest_trending_snapshot(state_root), newer)

    def test_latest_trending_snapshot_raises_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                latest_trending_snapshot(Path(directory))

    def test_load_trending_requires_add_and_drop_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "trending.json"
            snapshot.write_text(json.dumps({"add": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_trending(snapshot)

    def test_query_trending_players_enriches_and_filters(self):
        trending = {
            "add": [
                {"player_id": "1", "count": 500},
                {"player_id": "2", "count": 300},
                {"player_id": "3", "count": 100},
            ],
            "drop": [{"player_id": "2", "count": 50}],
        }
        players = [
            {"provider_id": "1", "full_name": "Alpha Runner",
             "fantasy_positions": ["RB"], "team": "AAA"},
            {"provider_id": "2", "full_name": "Beta Wideout",
             "fantasy_positions": ["WR"], "team": "BBB"},
        ]
        add_results = query_trending_players(trending, players, direction="add", limit=2)
        self.assertEqual([entry["provider_id"] for entry in add_results], ["1", "2"])
        self.assertEqual(add_results[0]["full_name"], "Alpha Runner")
        self.assertEqual(add_results[0]["count"], 500)
        # An unmatched provider id (no player snapshot entry) still appears,
        # with name/team fields left unresolved.
        self.assertEqual(
            [entry["provider_id"] for entry in query_trending_players(trending, players, direction="add", limit=10)],
            ["1", "2", "3"],
        )
        rb_only = query_trending_players(trending, players, direction="add", position="rb")
        self.assertEqual([entry["provider_id"] for entry in rb_only], ["1"])
        drop_results = query_trending_players(trending, players, direction="drop")
        self.assertEqual([entry["provider_id"] for entry in drop_results], ["2"])

    def test_query_trending_players_rejects_invalid_direction(self):
        with self.assertRaises(ValueError):
            query_trending_players({"add": [], "drop": []}, direction="sideways")

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

    def test_save_creates_draft_context_strategy_file_and_log(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            saved = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="WR Anchor",
                strategy={
                    "summary": "Start WR-heavy, then pivot into RB/QB value.",
                    "priority_positions": ["WR", "RB", "QB"],
                    "avoid_early": ["K", "DST"],
                    "round_plan": [{"rounds": "1-3", "targets": ["WR", "WR", "RB"]}],
                },
                questionnaire=[{"question": "Foundation", "answer": "WR anchor"}],
            )
            strategy_file = state_root / saved["draft_context_file"]
            self.assertTrue(strategy_file.exists())
            strategy_text = strategy_file.read_text(encoding="utf-8")
            self.assertIn("Agent rating:", strategy_text)
            self.assertIn("Sleeper_scoring.md", strategy_text)

            log_entries = load_strategy_creation_log(state_root, draft_style="sleeper_dynasty")
            self.assertEqual(len(log_entries), 1)
            self.assertEqual(log_entries[0]["strategy_id"], saved["strategy_id"])
            self.assertEqual(log_entries[0]["questionnaire"][0]["answer"], "WR anchor")
            self.assertEqual(load_strategy_creation_log(state_root, draft_style="sleeper_dynasty", limit=0), [])

    def test_manual_markdown_retirement_is_loaded_from_draft_context(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            saved = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                name="WR Anchor",
                strategy={
                    "priority_positions": ["WR", "RB"],
                    "avoid_early": ["K", "DST"],
                    "round_plan": [{"rounds": "1-2", "targets": ["WR", "RB"]}],
                },
            )
            strategy_file = state_root / saved["draft_context_file"]
            strategy_file.write_text(
                strategy_file.read_text(encoding="utf-8")
                .replace("in_effect: true", "in_effect: false")
                .replace("retired_reason: null", 'retired_reason: "User retired via markdown"')
                .replace("retired_at: null", 'retired_at: "2026-09-05T14:24:02+00:00"'),
                encoding="utf-8",
            )
            reloaded = strategies_for_session(state_root, league_id="league-1", season=2026)
            self.assertFalse(reloaded["strategies"][0]["in_effect"])
            self.assertEqual(reloaded["strategies"][0]["retired_reason"], "User retired via markdown")
            self.assertEqual(
                reloaded["strategies"][0]["creation_log_file"],
                "draft-context/sleeper_dynasty/logs/strategy-creation-log.jsonl",
            )

    def test_retire_draft_strategy_updates_state_and_appends_log(self):
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            saved = save_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="espn_snake",
                reverse_round=True,
                name="Third-Round Reversal WR Anchor",
                strategy={
                    "priority_positions": ["WR", "RB"],
                    "avoid_early": ["K", "DST"],
                    "round_plan": [{"rounds": "1-3", "targets": ["WR", "WR", "RB"]}],
                },
            )
            retired = retire_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                strategy_id=saved["strategy_id"],
                reason="Outperformed by later mock drafts",
            )
            self.assertFalse(retired["in_effect"])
            self.assertEqual(retired["retired_reason"], "Outperformed by later mock drafts")
            reloaded = strategies_for_session(state_root, league_id="league-1", season=2026)
            self.assertFalse(reloaded["strategies"][0]["in_effect"])
            log_entries = load_strategy_creation_log(state_root, draft_style="espn_snake")
            self.assertEqual([entry["event"] for entry in log_entries], ["created", "retired"])
            self.assertIn("retired_at", log_entries[1])

    def test_validate_strategy_flags_early_kicker_and_simulation_stays_clean(self):
        warnings = validate_draft_strategy(
            {
                "priority_positions": ["WR"],
                "round_plan": [{"rounds": "1-4", "targets": ["WR", "K"]}],
            },
            "sleeper_dynasty",
        )
        self.assertTrue(any("should not prioritize K" in warning for warning in warnings))
        late_warning = validate_draft_strategy(
            {
                "priority_positions": ["WR", "RB"],
                "avoid_early": ["K", "DST"],
                "round_plan": [{"rounds": "1-8", "targets": ["WR", "RB", "WR", "RB", "QB", "TE", "WR", "K"]}],
            },
            "sleeper_dynasty",
        )
        self.assertFalse(any("should not prioritize K" in warning for warning in late_warning))
        open_ended_warning = validate_draft_strategy(
            {
                "priority_positions": ["WR", "RB"],
                "round_plan": [{"rounds": "1+", "targets": ["WR", "RB", "WR", "QB", "K"]}],
            },
            "sleeper_dynasty",
        )
        self.assertTrue(any("should not prioritize K" in warning for warning in open_ended_warning))

        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            simulated = simulate_draft_strategy(
                state_root,
                league_id="league-1",
                season=2026,
                draft_style="sleeper_dynasty",
                seed=1,
            )
            self.assertEqual(simulated["creation_mode"], "simulation")
            self.assertEqual(simulated["validation_feedback"], [])
            self.assertGreaterEqual(simulated["agent_rating"], 80)

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
