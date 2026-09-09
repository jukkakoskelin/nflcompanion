import urllib.request
import json
import traceback

def fetch_player_news(player_id: str) -> str:
    query = """
    query {
      get_player_news(sport: "nfl", player_id: "%s") {
        metadata
      }
    }
    """ % player_id
    req = urllib.request.Request(
        'https://sleeper.app/graphql',
        data=json.dumps({'query': query}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.load(response)
            news_items = data.get("data", {}).get("get_player_news", [])
            if news_items:
                metadata = news_items[0].get("metadata", {})
                title = metadata.get("title", "")
                desc = metadata.get("description", "")
                if title and desc:
                    return f"{title}: {desc}"
                elif desc:
                    return desc
                elif title:
                    return title
    except Exception as e:
        print(f"Failed to fetch news for {player_id}: {e}")
        traceback.print_exc()
    return "New update available"

print(fetch_player_news("4314"))
print(fetch_player_news("bad_id"))
