from abc import ABC, abstractmethod
import urllib.request
import json

class Provider(ABC):
    @abstractmethod
    def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
        """Returns a list of player IDs currently on the given user's roster."""
        pass

class SleeperProvider(Provider):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
        url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            rosters = json.load(response)
        
        for roster in rosters:
            if roster.get("owner_id") == user_id:
                return roster.get("players", [])
        return []

def get_provider(platform: str) -> Provider:
    if platform == "sleeper":
        return SleeperProvider()
    raise ValueError(f"Unsupported platform: {platform}")
