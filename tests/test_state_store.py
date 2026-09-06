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
            self.assertIn("## Agent workflow", strategy_text)
            self.assertIn("draft-strategy-orchestrator", strategy_text)
            self.assertIn("docs/draft-strategy-agents/orchestrator.md", strategy_text)
            self.assertEqual(saved["collaborating_agents"]["orchestrator"], "draft-strategy-orchestrator")
            self.assertEqual(saved["agent_workflow"]["orchestrator"]["prompt_file"], "docs/draft-strategy-agents/orchestrator.md")

            log_entries = load_strategy_creation_log(state_root, draft_style="sleeper_dynasty")
            self.assertEqual(len(log_entries), 1)
            self.assertEqual(log_entries[0]["strategy_id"], saved["strategy_id"])
            self.assertEqual(log_entries[0]["questionnaire"][0]["answer"], "WR anchor")
            self.assertEqual(log_entries[0]["agent_workflow"]["orchestrator"]["agent"], "draft-strategy-orchestrator")
            self.assertEqual(load_strategy_creation_log(state_root, draft_style="sleeper_dynasty", limit=0), [])
            review_log = (state_root / saved["creation_review_log_file"]).read_text(encoding="utf-8")
            self.assertIn("# Draft strategy creation log", review_log)
            self.assertIn("## Created: WR Anchor", review_log)
            self.assertIn("### Questionnaire", review_log)

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
            review_log = (state_root / retired["creation_review_log_file"]).read_text(encoding="utf-8")
            self.assertIn("## Retired: Third-Round Reversal WR Anchor", review_log)
            self.assertIn("Retirement reason: Outperformed by later mock drafts", review_log)

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
            self.assertEqual(simulated["agent_workflow"]["agents"][0]["role"], "interviewer")

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

    # ---------------------------------------------------------------------------
    # Dynasty-specific tests
    # ---------------------------------------------------------------------------

    def test_dynasty_strategy_saves_to_sleeper_dynasty_folder(self):
        """Strategy Markdown file must land in draft-context/sleeper_dynasty/strategies/."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            saved = save_draft_strategy(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                draft_style="sleeper_dynasty",
                name="WR Anchor Superflex Early QB",
                strategy={
                    "summary": "Open with elite WR, take a top QB early in Superflex.",
                    "anchor_position": "WR",
                    "superflex_plan": "Take a top-5 QB by round 3 for Superflex.",
                    "dynasty_horizon": "balanced",
                    "taxi_squad_plan": "Target 2 rookies in rounds 22-25.",
                    "priority_positions": ["WR", "QB", "RB"],
                    "avoid_early": ["K", "DST"],
                    "round_plan": [
                        {"rounds": "1-3", "targets": ["WR", "QB", "RB"], "focus": "Anchor WR + early QB."},
                        {"rounds": "4-10", "targets": ["RB", "WR", "TE"], "focus": "Build depth."},
                        {"rounds": "11-25", "targets": ["RB", "WR"], "focus": "Youth and taxi targets."},
                    ],
                    "notes": ["Full PPR rewards high-target WRs in dynasty."],
                    "mock_draft_review": ["Did the anchor WR have locked-in target share?"],
                },
            )
            draft_context_file = saved["draft_context_file"]
            self.assertIn("sleeper_dynasty", draft_context_file)
            self.assertIn("strategies", draft_context_file)
            md_path = Path(directory) / draft_context_file
            self.assertTrue(md_path.exists(), f"Strategy Markdown not found: {md_path}")
            log_path = Path(directory) / saved["creation_log_file"]
            self.assertTrue(log_path.exists(), f"Creation log not found: {log_path}")

    def test_dynasty_validation_warns_without_superflex_plan(self):
        """validate_draft_strategy should warn when superflex_plan is missing for sleeper_dynasty."""
        from nflcompanion.state_store import validate_draft_strategy
        strategy = {
            "priority_positions": ["WR", "QB", "RB"],
            "avoid_early": ["K", "DST"],
            "round_plan": [{"rounds": "1-3", "targets": ["WR", "QB"]}],
            # superflex_plan deliberately omitted
            "dynasty_horizon": "balanced",
        }
        warnings = validate_draft_strategy(strategy, "sleeper_dynasty")
        self.assertTrue(
            any("superflex_plan" in w for w in warnings),
            f"Expected superflex_plan warning; got: {warnings}",
        )

    def test_dynasty_validation_warns_without_dynasty_horizon(self):
        """validate_draft_strategy should warn when dynasty_horizon is missing for sleeper_dynasty."""
        from nflcompanion.state_store import validate_draft_strategy
        strategy = {
            "priority_positions": ["WR", "QB"],
            "avoid_early": ["K", "DST"],
            "round_plan": [{"rounds": "1-3", "targets": ["WR", "QB"]}],
            "superflex_plan": "Take QB by round 3.",
            # dynasty_horizon deliberately omitted
        }
        warnings = validate_draft_strategy(strategy, "sleeper_dynasty")
        self.assertTrue(
            any("dynasty_horizon" in w for w in warnings),
            f"Expected dynasty_horizon warning; got: {warnings}",
        )

    def test_dynasty_validation_no_extra_warnings_for_full_strategy(self):
        """A complete dynasty strategy should produce no dynasty-specific warnings."""
        from nflcompanion.state_store import validate_draft_strategy
        strategy = {
            "priority_positions": ["WR", "QB", "RB"],
            "avoid_early": ["K", "DST"],
            "round_plan": [{"rounds": "1-3", "targets": ["WR", "QB"]}],
            "superflex_plan": "Take QB by round 3.",
            "dynasty_horizon": "balanced",
        }
        warnings = validate_draft_strategy(strategy, "sleeper_dynasty")
        dynasty_warnings = [w for w in warnings if "superflex" in w or "dynasty_horizon" in w]
        self.assertEqual(dynasty_warnings, [], f"Unexpected dynasty warnings: {dynasty_warnings}")

    def test_dynasty_rating_bonus_for_superflex_and_taxi(self):
        """rate_draft_strategy should give extra points for superflex_plan, taxi_squad_plan, dynasty_horizon."""
        from nflcompanion.state_store import rate_draft_strategy
        # Minimal base strategy: 55 base + 8 summary + 15 round_plan + 10 priority = 88
        # Deliberately omit notes (+7) and mock_draft_review (+5) to stay well below the 95 cap.
        base_strategy = {
            "summary": "WR Anchor.",
            "priority_positions": ["WR", "QB"],
            "avoid_early": ["K", "DST"],
            "round_plan": [{"rounds": "1-3", "targets": ["WR", "QB"]}],
        }
        dynasty_strategy = {
            **base_strategy,
            "superflex_plan": "Early QB.",     # +5
            "taxi_squad_plan": "2 rookies.",    # +3
            "dynasty_horizon": "balanced",      # +2
        }
        dynasty_base_score = rate_draft_strategy(base_strategy, draft_style="sleeper_dynasty", validation_feedback=[])
        dynasty_full_score = rate_draft_strategy(dynasty_strategy, draft_style="sleeper_dynasty", validation_feedback=[])
        espn_base_score = rate_draft_strategy(base_strategy, draft_style="espn_snake", validation_feedback=[])
        # Dynasty bonus fields must push the full score above the base
        self.assertGreater(
            dynasty_full_score, dynasty_base_score,
            f"dynasty_full={dynasty_full_score} should be > dynasty_base={dynasty_base_score}"
        )
        # ESPN and dynasty should score the same base (no dynasty-specific keys present)
        self.assertEqual(espn_base_score, dynasty_base_score)

    def test_agent_workflow_uses_dynasty_strategy_agent_for_sleeper(self):
        """_agent_workflow should reference sleeper-dynasty-strategy-agent for sleeper_dynasty."""
        from nflcompanion.state_store import _agent_workflow, _DEFAULT_AGENT_ROLES_BY_STYLE
        session_config = {
            "league_id": "sleeper-10-dynasty-2026",
            "season": 2026,
            "draft_style": "sleeper_dynasty",
            "platform": "sleeper",
            "draft_type": "dynasty",
            "reverse_round": False,
        }
        collaborating = _DEFAULT_AGENT_ROLES_BY_STYLE["sleeper_dynasty"]
        workflow = _agent_workflow(session_config, collaborating)
        strategy_agent_entry = next(
            (a for a in workflow["agents"] if a["role"] == "strategy_agent"), None
        )
        self.assertIsNotNone(strategy_agent_entry)
        self.assertIn("sleeper-dynasty", strategy_agent_entry["agent"])
        self.assertIn("sleeper-dynasty-strategy-agent.md", strategy_agent_entry["prompt_file"])

    def test_agent_workflow_uses_espn_strategy_agent_for_espn(self):
        """_agent_workflow should reference espn-snake-strategy-agent for espn_snake."""
        from nflcompanion.state_store import _agent_workflow, _DEFAULT_AGENT_ROLES_BY_STYLE
        session_config = {
            "league_id": "espn-16-2026",
            "season": 2026,
            "draft_style": "espn_snake",
            "platform": "espn",
            "draft_type": "snake",
            "reverse_round": False,
        }
        collaborating = _DEFAULT_AGENT_ROLES_BY_STYLE["espn_snake"]
        workflow = _agent_workflow(session_config, collaborating)
        strategy_agent_entry = next(
            (a for a in workflow["agents"] if a["role"] == "strategy_agent"), None
        )
        self.assertIsNotNone(strategy_agent_entry)
        self.assertIn("espn-snake", strategy_agent_entry["agent"])
        self.assertIn("espn-strategy-agent.md", strategy_agent_entry["prompt_file"])

    def test_dynasty_workflow_success_criteria_mention_superflex(self):
        """Dynasty workflow success_criteria must mention Superflex QB plan."""
        from nflcompanion.state_store import _agent_workflow, _DEFAULT_AGENT_ROLES_BY_STYLE
        session_config = {
            "league_id": "sleeper-10-dynasty-2026",
            "season": 2026,
            "draft_style": "sleeper_dynasty",
            "platform": "sleeper",
            "draft_type": "dynasty",
            "reverse_round": False,
        }
        workflow = _agent_workflow(session_config, _DEFAULT_AGENT_ROLES_BY_STYLE["sleeper_dynasty"])
        criteria_text = " ".join(workflow["success_criteria"])
        self.assertIn("Superflex", criteria_text)

    def test_dynasty_simulate_returns_valid_strategies(self):
        """simulate_draft_strategy for sleeper_dynasty should produce at least one strategy."""
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory) / "state"
            result = simulate_draft_strategy(
                state_root,
                league_id="sleeper-10-dynasty-2026",
                season=2026,
                draft_style="sleeper_dynasty",
                reverse_round=False,
                seed=42,
            )
            self.assertIn("strategy_id", result)
            draft_context_file = result.get("draft_context_file", "")
            self.assertIn("sleeper_dynasty", draft_context_file)

