from abc import ABC, abstractmethod
import urllib.request
import json
from typing import Any
import time
import socket

def retry(times=3, delay=1):
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= times:
                        raise e
                    time.sleep(delay)
            return func(*args, **kwargs)
        return newfn
    return decorator

class Provider(ABC):
    @abstractmethod
    def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
        """Returns a list of player IDs currently on the given user's roster."""
        pass
        
    @abstractmethod
    def get_all_rostered_players(self, league_id: str) -> set[str]:
        """Returns a set of all player IDs currently on any roster in the league."""
        pass

    def get_free_agents(self, league_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Returns a list of free agents available in the league."""
        return []

    def get_player_fallback_metadata(self) -> dict[str, dict[str, Any]]:
        """Returns a dict mapping player IDs to a fallback metadata dict (e.g. from a third-party API) to use if local data is missing."""
        return {}

    def get_projections(self, week: int, year: int | None = None) -> dict[str, Any]:
        """Returns a dictionary mapping player IDs to their projected points."""
        return {}

class SleeperProvider(Provider):
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
        rosters = self.get_league_rosters(league_id)
        for roster in rosters:
            if roster.get("owner_id") == user_id:
                return roster.get("players", [])
        return []

    def get_all_rostered_players(self, league_id: str) -> set[str]:
        rosters = self.get_league_rosters(league_id)
        rostered = set()
        for r in rosters:
            rostered.update(r.get("players", []))
        return rostered

    @retry(times=3, delay=1)
    def get_nfl_state(self) -> dict[str, Any]:
        url = "https://api.sleeper.app/v1/state/nfl"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.load(response)

    @retry(times=3, delay=1)
    def _fetch_projections(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            projections = json.load(response)
            return {pid: p.get("pts_half_ppr", 0.0) for pid, p in projections.items()}

    def get_projections(self, week: int, year: int | None = None) -> dict[str, Any]:
        if year is None:
            state = self.get_nfl_state()
            year = int(state.get("season", 2026))
        url = f"https://api.sleeper.app/v1/projections/nfl/regular/{year}/{week}"
        try:
            return self._fetch_projections(url)
        except Exception:
            return {}

    @retry(times=3, delay=1)
    def get_league_rosters(self, league_id: str) -> list[dict[str, Any]]:
        url = f"https://api.sleeper.app/v1/league/{league_id}/rosters"
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "nflcompanion/0.1"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return json.load(response)

    @retry(times=3, delay=1)
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

def get_provider(platform: str, config: dict[str, Any] | None = None) -> Provider:
    if platform == "sleeper":
        return SleeperProvider()
    elif platform == "espn":
        import espn_api.football
        if not config:
            raise ValueError("Config is required for ESPNProvider")
        class ESPNProvider(Provider):
            def __init__(self, config: dict[str, Any]):
                league_id = int(config.get("espn_league_id"))
                year = int(config.get("espn_year", 2026))
                espn_s2 = config.get("espn_s2")
                swid = config.get("swid")
                self.league = espn_api.football.League(league_id=league_id, year=year, espn_s2=espn_s2, swid=swid)

            def get_user_roster(self, league_id: str, user_id: str) -> list[str]:
                team_id = int(user_id)
                for team in self.league.teams:
                    if team.team_id == team_id:
                        return [str(player.playerId) for player in team.roster]
                return []
                
            def get_all_rostered_players(self, league_id: str) -> set[str]:
                rostered = set()
                for team in self.league.teams:
                    for player in team.roster:
                        rostered.add(str(player.playerId))
                return rostered

            def get_nfl_state(self) -> dict[str, Any]:
                return {
                    "season_type": "regular",
                    "leg": self.league.current_week
                }
                
            def get_projections(self, week: int, year: int | None = None) -> dict[str, Any]:
                # For ESPN, projections are usually attached to the box_scores or player objects.
                # It's easier to retrieve them directly from get_user_matchup.
                return {}

            def get_user_matchup(self, league_id: str, user_id: str, week: int) -> dict[str, Any]:
                team_id = int(user_id)
                box_scores = self.league.box_scores(week)
                
                user_matchup = None
                opponent_matchup = None
                
                for matchup in box_scores:
                    if matchup.home_team.team_id == team_id:
                        user_matchup = matchup.home_lineup
                        opponent_matchup = matchup.away_lineup
                        break
                    elif matchup.away_team.team_id == team_id:
                        user_matchup = matchup.away_lineup
                        opponent_matchup = matchup.home_lineup
                        break
                        
                if user_matchup is None:
                    raise ValueError(f"Could not find matchup for team {team_id} in week {week}")
                    
                def format_lineup(lineup):
                    if not lineup:
                        return None
                    
                    starters = []
                    players = []
                    points = 0.0
                    projected_points = 0.0
                    player_points = {}
                    player_projected = {}
                    
                    for p in lineup:
                        pid = str(p.playerId)
                        players.append(pid)
                        pts = getattr(p, 'points', 0.0)
                        proj = getattr(p, 'projected_points', 0.0)
                        
                        player_points[pid] = pts
                        player_projected[pid] = proj
                        
                        if getattr(p, 'slot_position', '') not in ('BE', 'IR'):
                            starters.append(pid)
                            points += pts
                            projected_points += proj
                            
                    return {
                        "starters": starters,
                        "players": players,
                        "points": points,
                        "projected_points": projected_points,
                        "player_points": player_points,
                        "player_projected": player_projected
                    }
                    
                return {
                    "user": format_lineup(user_matchup),
                    "opponent": format_lineup(opponent_matchup)
                }
                
            def get_player_fallback_metadata(self) -> dict[str, dict[str, Any]]:
                metadata = {}
                for team in self.league.teams:
                    for p in team.roster:
                        pid = str(p.playerId)
                        metadata[pid] = {
                            "player_id": pid,
                            "full_name": p.name,
                            "position": p.position,
                            "team": p.proTeam,
                            "injury_status": p.injuryStatus,
                            "is_unmapped_espn": True
                        }
                return metadata

            def get_free_agents(self, league_id: str, limit: int = 100) -> list[dict[str, Any]]:
                # Fetch more to account for filtered positions
                fetch_size = limit + 50
                try:
                    free_agents = self.league.free_agents(size=fetch_size)
                except Exception:
                    # Some ESPN leagues might not support free_agents or might throw on error
                    return []
                    
                results = []
                for p in free_agents:
                    if p.position in ("D/ST", "K"):
                        continue
                    
                    results.append({
                        "player_id": str(p.playerId),
                        "full_name": p.name,
                        "position": p.position,
                        "team": getattr(p, 'proTeam', ''),
                        "injury_status": getattr(p, 'injuryStatus', ''),
                        "projected_points": getattr(p, 'projected_points', 0.0),
                        "total_points": getattr(p, 'total_points', 0.0),
                        "percent_owned": getattr(p, 'percent_owned', 0.0),
                        "percent_started": getattr(p, 'percent_started', 0.0),
                    })
                    if len(results) >= limit:
                        break
                return results

        return ESPNProvider(config)
    raise ValueError(f"Unsupported platform: {platform}")

