from abc import ABC, abstractmethod
import urllib.request
import json
from typing import Any

class Provider(ABC):
    @abstractmethod
    def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
        """Returns a list of player IDs currently on the given user's roster."""
        pass

class SleeperProvider(Provider):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
        rosters = self.get_league_rosters(league_id)
        for roster in rosters:
            if roster.get("owner_id") == user_id:
                return roster.get("players", [])
        return []

    def get_nfl_state(self) -> dict[str, Any]:
        url = "https://api.sleeper.app/v1/state/nfl"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.load(response)

    def get_league_rosters(self, league_id: str) -> list[dict[str, Any]]:
        url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.load(response)

    def get_matchups(self, league_id: str, week: int) -> list[dict[str, Any]]:
        url = f"https://api.sleeper.app/v1/league/{league_id}/matchups/{week}"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.load(response)

    def get_user_matchup(self, league_id: str, user_id: str, week: int) -> dict[str, Any]:
        rosters = self.get_league_rosters(league_id)
        user_roster_id = None
        for r in rosters:
            if r.get("owner_id") == user_id:
                user_roster_id = r.get("roster_id")
                break
        
        if not user_roster_id:
            raise ValueError(f"Could not find roster for user {user_id} in league {league_id}")

        matchups = self.get_matchups(league_id, week)
        user_matchup = None
        for m in matchups:
            if m.get("roster_id") == user_roster_id:
                user_matchup = m
                break
        
        if not user_matchup:
            raise ValueError(f"Could not find matchup for roster {user_roster_id} in week {week}")

        matchup_id = user_matchup.get("matchup_id")
        opponent_matchup = None
        for m in matchups:
            if m.get("matchup_id") == matchup_id and m.get("roster_id") != user_roster_id:
                opponent_matchup = m
                break

        return {
            "user": user_matchup,
            "opponent": opponent_matchup
        }

def get_provider(platform: str) -> Provider:
    if platform == "sleeper":
        return SleeperProvider()
    raise ValueError(f"Unsupported platform: {platform}")
