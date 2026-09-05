"""Unit tests for Antigravity lifecycle hook scripts."""

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.hooks.check_guardrails_stop import main as stop_main
from scripts.hooks.pre_invocation_trending import get_trending_summary, main as pre_invocation_main


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.state_root = Path(self.temp_dir.name)

    def test_pre_invocation_trending_with_missing_state(self):
        # When no state exists and fetch fails (mocked), summary returns None
        with patch("scripts.hooks.pre_invocation_trending.fetch_trending", side_effect=Exception("network error")):
            summary = get_trending_summary(self.state_root)
            self.assertIsNone(summary)

    def test_pre_invocation_trending_formats_summary(self):
        # Create dummy trending snapshot
        trending_dir = self.state_root / "players" / "trending" / "raw"
        trending_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": "sleeper",
            "retrieved_at": "2026-09-05T12:00:00Z",
            "lookback_hours": 24,
            "limit": 25,
            "add": [{"player_id": "4034", "count": 120}],
            "drop": [{"player_id": "4035", "count": 80}],
        }
        (trending_dir / "sleeper-trending-2026-09-05T120000000Z.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

        summary = get_trending_summary(self.state_root)
        self.assertIsNotNone(summary)
        self.assertIn("Sleeper trending players", summary)
        self.assertIn("Top adds:", summary)
        self.assertIn("Top drops:", summary)

    def test_pre_invocation_main_emits_json(self):
        with patch("sys.stdin", io.StringIO("{}")):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = pre_invocation_main()
                self.assertEqual(exit_code, 0)
                output = json.loads(mock_stdout.getvalue())
                self.assertIn("injectSteps", output)

    def test_check_guardrails_stop_runs(self):
        with patch("sys.stdin", io.StringIO("{}")):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                exit_code = stop_main()
                self.assertEqual(exit_code, 0)
                output = json.loads(mock_stdout.getvalue())
                # Should be valid JSON object (either {} or {"decision": "continue", ...})
                self.assertIsInstance(output, dict)


if __name__ == "__main__":
    unittest.main()
