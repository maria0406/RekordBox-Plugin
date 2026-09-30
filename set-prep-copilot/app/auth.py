"""Authorization Code with PKCE flow, driven by FastAPI routes instead of a
blocking local HTTP server (the app itself IS the local server the DJ's
browser talks to). Tokens are cached in a local JSON file (gitignored,
chmod 600) since this is a single-user local app, not a multi-tenant one.
Never logs or returns a raw access/refresh token to the browser or terminal.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time

import requests

from . import config

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorize_url(challenge: str, state: str) -> str:
    from urllib.parse import urlencode

    query = urlencode(
        {
            "client_id": config.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            "state": state,
            "scope": " ".join(config.SPOTIFY_SCOPES),
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def exchange_code_for_tokens(code: str, verifier: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": config.SPOTIFY_CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            "code_verifier": verifier,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    token_data["obtained_at"] = time.time()
    return token_data


def refresh_tokens(refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": config.SPOTIFY_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    if "refresh_token" not in token_data:
        token_data["refresh_token"] = refresh_token
    token_data["obtained_at"] = time.time()
    return token_data


def load_cached_tokens() -> dict | None:
    if not config.TOKEN_CACHE_PATH.exists():
        return None
    try:
        return json.loads(config.TOKEN_CACHE_PATH.read_text())
    except (ValueError, OSError):
        return None


def save_cached_tokens(token_data: dict) -> None:
    config.TOKEN_CACHE_PATH.write_text(json.dumps(token_data, indent=2))
    os.chmod(config.TOKEN_CACHE_PATH, 0o600)


def clear_cached_tokens() -> None:
    if config.TOKEN_CACHE_PATH.exists():
        config.TOKEN_CACHE_PATH.unlink()


def is_authenticated() -> bool:
    tokens = load_cached_tokens()
    return bool(tokens and tokens.get("access_token"))


def get_access_token() -> str:
    """Current cached access token, refreshing first if we're past its expiry."""
    tokens = load_cached_tokens()
    if not tokens:
        raise RuntimeError("Not authenticated with Spotify yet.")

    expires_in = tokens.get("expires_in", 3600)
    obtained_at = tokens.get("obtained_at", 0)
    if time.time() > obtained_at + expires_in - 60:
        tokens = refresh_tokens(tokens["refresh_token"])
        save_cached_tokens(tokens)

    return tokens["access_token"]


def force_refresh() -> str:
    """Used after a live 401 to refresh once and retry, per the explorer script's pattern."""
    tokens = load_cached_tokens()
    if not tokens:
        raise RuntimeError("Not authenticated with Spotify yet.")
    tokens = refresh_tokens(tokens["refresh_token"])
    save_cached_tokens(tokens)
    return tokens["access_token"]
