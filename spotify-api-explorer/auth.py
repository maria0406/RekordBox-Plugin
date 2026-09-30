"""Authorization Code with PKCE flow for the Spotify Web API.

Never logs or persists a raw access/refresh token to stdout. Tokens are cached
on disk in .token_cache.json (gitignored) so repeat runs don't need a fresh
browser login.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()
TOKEN_CACHE_PATH = HERE / ".token_cache.json"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"

SCOPES = [
    "user-read-private",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-library-read",
    "user-read-currently-playing",
    "user-read-playback-state",
]


def _require_client_id() -> None:
    if not CLIENT_ID:
        raise SystemExit(
            "SPOTIFY_CLIENT_ID is not set. Paste your Spotify app's Client ID "
            "into spotify-api-explorer/.env and re-run."
        )


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


class _CallbackServer(http.server.HTTPServer):
    auth_code: str | None = None
    auth_error: str | None = None
    expected_state: str = ""


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib method name)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        server: _CallbackServer = self.server  # type: ignore[assignment]

        state = params.get("state", [""])[0]
        if state != server.expected_state:
            server.auth_error = "state mismatch"
        elif "error" in params:
            server.auth_error = params["error"][0]
        else:
            server.auth_code = params.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = (
            "<html><body><h2>Spotify login complete.</h2>"
            "<p>You can close this tab and return to the terminal.</p>"
            "</body></html>"
        )
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):  # silence default stderr logging
        return


def _run_local_server_and_get_code(state: str, port: int) -> str:
    server = _CallbackServer(("127.0.0.1", port), _CallbackHandler)
    server.expected_state = state
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=300)

    if server.auth_error:
        raise SystemExit(f"Spotify authorization failed: {server.auth_error}")
    if not server.auth_code:
        raise SystemExit("Timed out waiting for the Spotify login callback.")
    return server.auth_code


def _authorize_new_tokens() -> dict:
    _require_client_id()
    verifier, challenge = _make_pkce_pair()
    state = secrets.token_urlsafe(16)

    query = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "scope": " ".join(SCOPES),
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    auth_url = f"{AUTHORIZE_URL}?{query}"

    port = int(urllib.parse.urlparse(REDIRECT_URI).port or 8888)
    print(f"Opening your browser to log in to Spotify (listening on 127.0.0.1:{port})...")
    webbrowser.open(auth_url)

    code = _run_local_server_and_get_code(state, port)

    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    token_data["obtained_at"] = time.time()
    return token_data


def _refresh_tokens(refresh_token: str) -> dict:
    _require_client_id()
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    # Spotify doesn't always return a new refresh_token; keep the old one if so.
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = refresh_token
    token_data["obtained_at"] = time.time()
    return token_data


def _load_cache() -> dict | None:
    if not TOKEN_CACHE_PATH.exists():
        return None
    import json

    try:
        return json.loads(TOKEN_CACHE_PATH.read_text())
    except (ValueError, OSError):
        return None


def _save_cache(token_data: dict) -> None:
    import json

    TOKEN_CACHE_PATH.write_text(json.dumps(token_data, indent=2))
    os.chmod(TOKEN_CACHE_PATH, 0o600)


class SpotifyAuth:
    """Holds the current access token and knows how to refresh it once."""

    def __init__(self):
        self._tokens = _load_cache()
        if self._tokens is None:
            self._tokens = _authorize_new_tokens()
            _save_cache(self._tokens)

    @property
    def access_token(self) -> str:
        return self._tokens["access_token"]

    def refresh(self) -> None:
        self._tokens = _refresh_tokens(self._tokens["refresh_token"])
        _save_cache(self._tokens)

    def auth_header(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}
