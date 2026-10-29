import io
import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from nflcompanion.providers import SleeperProvider, get_provider


class TestProviderProjectionDefaults(unittest.TestCase):
    def test_sleeper_preserves_missing_projection_and_real_zero(self):
        provider = SleeperProvider()
        response = io.BytesIO(
            json.dumps(
                {
                    "1": {"pts_half_ppr": 0.0},
                    "2": {},
                }
            ).encode()
        )

        with patch("nflcompanion.providers.urllib.request.urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value = response
            projections = provider._fetch_projections("https://example.test/projections")

        self.assertEqual(projections, {"1": 0.0, "2": None})

    def test_espn_preserves_missing_player_projection(self):
        league = MagicMock()
        league.box_scores.return_value = [
            SimpleNamespace(
                home_team=SimpleNamespace(team_id=1),
                away_team=SimpleNamespace(team_id=2),
                home_lineup=[
                    SimpleNamespace(
                        playerId=101,
                        points=0.0,
                        slot_position="QB",
                        injuryStatus="ACTIVE",
                    )
                ],
                away_lineup=[],
            )
        ]
        espn_api = types.ModuleType("espn_api")
        football = types.ModuleType("espn_api.football")
        football.League = MagicMock(return_value=league)
        espn_api.football = football

        with patch.dict(
            sys.modules,
            {"espn_api": espn_api, "espn_api.football": football},
        ):
            provider = get_provider("espn", {"espn_league_id": 1})
            matchup = provider.get_user_matchup("league", "1", 8)

        self.assertEqual(matchup["user"]["player_projected"], {"101": None})


if __name__ == "__main__":
    unittest.main()
