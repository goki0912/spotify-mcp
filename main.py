import logging
import os
import random
import webbrowser
from typing import Literal

import spotipy
from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import Field
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("spotify_mcp")

load_dotenv()

client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = "http://127.0.0.1:8888/callback"

SCOPE = "user-modify-playback-state user-read-playback-state user-library-read"

# ここはマジで適当。
EASY_GENRES = [
    "ambient",
    "chill-out",
    "acoustic",
    "classical",
    "piano",
    "lofi",
    "new age",
    "soundtrack",
]
MEDIUM_GENRES = [
    "jazz",
    "funk",
    "downtempo",
    "lounge",
    "fusion",
    "nu jazz",
    "electro jazz",
    "instrumental",
]
HARD_GENRES = [
    "techno",
    "trance",
    "minimal",
    "drum and bass",
    "idm",
    "deep house",
    "electronic",
    "synthwave",
]


if not all([client_id, client_secret, redirect_uri]):
    raise ValueError("Spotify API credentials not found in environment variables.")

cache_handler = CacheFileHandler()
sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope=SCOPE,
    cache_handler=cache_handler,
)

app = FastMCP(name="spotify mcp", port=8888)


def get_spotify_client():
    token_info = sp_oauth.cache_handler.get_cached_token()
    token_info = sp_oauth.validate_token(token_info)
    if not token_info:
        logger.warning("No cached token found. Please authenticate by visiting /login")
        raise Exception("Not authenticated. Please visit /login to authenticate.")
    return spotipy.Spotify(auth=token_info["access_token"])


@app.tool(name="login", description="Spotifyにログインして認証トークンを取得します。")
def login():
    webbrowser.open(sp_oauth.get_authorize_url())
    return "ブラウザが開きます。ログインしてください。"


@app.custom_route("/callback", methods=["GET"])
async def callback(request: Request):
    code = request.query_params.get("code")
    if code:
        try:
            sp_oauth.get_access_token(code, as_dict=True)
            logger.info("Successfully authenticated and cached token.")
            return JSONResponse(content={"message": "Authentication successful!"})
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return JSONResponse(content={"error": "Could not get access token."})
    return JSONResponse(content={"error": "No code found in callback."})


@app.tool(
    name="play_song_by_difficulty",
    description="""
    このToolはAIエージェントがプログラミングコードを実装するときに必ず起動します。
    これから実行するタスクの難易度に応じてジャンルを変えて曲を再生します。
    そうすることで利用者がAIエージェントが何をしているかを理解しやすくします。
    引数: difficulty ('easy'|'medium'|'hard')
    """,
)
def play_song_by_difficulty(
    difficulty: Literal["easy", "medium", "hard"] = Field(
        description="難易度を指定します。'easy', 'medium', 'hard' のいずれかを指定してください。"
    ),
):
    try:
        sp = get_spotify_client()

        if difficulty == "easy":
            genre_list = EASY_GENRES
        elif difficulty == "medium":
            genre_list = MEDIUM_GENRES
        elif difficulty == "hard":
            genre_list = HARD_GENRES

        genre = random.choice(genre_list)

        current = sp.current_user_playing_track()
        if current is not None and "item" in current:
            current_artist_id = current["item"]["artists"][0]["id"]
            current_artist = sp.artist(current_artist_id)
            if (
                current_artist is not None
                and "genres" in current_artist
                and current_artist["genres"]
            ):
                current_genres = [g.lower() for g in current_artist["genres"]]
                if any(g in genre_list for g in current_genres):
                    track_name = current["item"]["name"]
                    artist_name = current["item"]["artists"][0]["name"]
                    return {
                        "message": f"既に難易度『{difficulty}』の曲（{track_name} / {artist_name}）が再生中なので、そのままにします。"
                    }

        results = sp.search(q=f"genre:{genre}", type="track", limit=50)
        tracks = (
            results["tracks"]["items"]
            if results and "tracks" in results and "items" in results["tracks"]
            else []
        )
        if not tracks:
            return {"error": f"ジャンル '{genre}' の曲が見つかりませんでした。"}

        track = random.choice(tracks)
        track_uri = track["uri"]
        track_name = track["name"]
        artist_name = track["artists"][0]["name"]

        devices_response = sp.devices()
        if not devices_response or not devices_response.get("devices"):
            webbrowser.open("https://open.spotify.com/")
            return {
                "error": "Spotifyデバイスが見つかりません。SpotifyアプリまたはWebプレイヤーを起動してください。"
            }

        active_device = next(
            (d for d in devices_response["devices"] if d["is_active"]), None
        )
        if not active_device:
            if devices_response["devices"]:
                active_device = devices_response["devices"][0]
                logger.info(
                    f"No active device, falling back to first available device: {active_device['name']}"
                )
            else:
                return {
                    "error": "Spotifyデバイスが見つかりません。Spotifyアプリを起動してください。"
                }

        device_id = active_device["id"]
        sp.start_playback(device_id=device_id, uris=[track_uri])
        logger.info(
            f"Started playing '{track_name}' by {artist_name} for difficulty '{difficulty}' on device {active_device['name']}"
        )
        return {
            "message": f"難易度: {difficulty} → 再生中: {track_name} / {artist_name}"
        }

    except Exception as e:
        logger.error(f"Error in play_song_by_difficulty: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    app.run(transport="streamable-http")
