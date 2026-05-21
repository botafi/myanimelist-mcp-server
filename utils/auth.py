from __future__ import annotations

import http.server
import os
import secrets
import socketserver
import time
import urllib.parse
import webbrowser
from typing import Dict, Optional

import httpx
from dotenv import load_dotenv

from utils.mal_client import safe_error
from utils.token_store import StoredTokens, TokenStore

load_dotenv()

_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_expires_at: Optional[float] = None

REDIRECT_URI = os.getenv("MAL_REDIRECT_URI", "http://localhost:8080/callback")
CALLBACK_HOST = os.getenv("MAL_CALLBACK_HOST", "127.0.0.1")
CALLBACK_PORT = int(os.getenv("MAL_CALLBACK_PORT", "8080"))
CALLBACK_TIMEOUT_SECONDS = int(os.getenv("MAL_CALLBACK_TIMEOUT_SECONDS", "300"))
CALLBACK_CODE = None
CALLBACK_STATE = None
TOKEN_STORE = TokenStore()


def _client_id() -> str:
    value = os.getenv("MAL_CLIENT_ID")
    if not value:
        raise ValueError("MAL_CLIENT_ID is required. Create an app at https://myanimelist.net/apiconfig and set it in the environment.")
    return value


def _client_secret() -> str:
    value = os.getenv("MAL_CLIENT_SECRET")
    if not value:
        raise ValueError("MAL_CLIENT_SECRET is required for MyAnimeList OAuth token exchange/refresh.")
    return value


def get_new_code_verifier() -> str:
    return secrets.token_urlsafe(64)


async def get_authorization_url() -> tuple[str, str, str]:
    code_verifier = get_new_code_verifier()
    code_challenge = code_verifier  # MAL currently supports plain PKCE.
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "plain",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    url = "https://myanimelist.net/v1/oauth2/authorize?" + urllib.parse.urlencode(params)
    return url, code_verifier, state


class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def do_GET(self):
        global CALLBACK_CODE, CALLBACK_STATE
        query = urllib.parse.urlparse(self.path).query
        query_components = urllib.parse.parse_qs(query)
        CALLBACK_CODE = query_components.get("code", [None])[0]
        CALLBACK_STATE = query_components.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Authorization code received. You can close this window and return to Hermes.")


async def capture_authorization_code(expected_state: str) -> str:
    global CALLBACK_CODE, CALLBACK_STATE
    CALLBACK_CODE = None
    CALLBACK_STATE = None
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer((CALLBACK_HOST, CALLBACK_PORT), CallbackHandler) as httpd:
            httpd.timeout = 5
            print(f"HTTP server started on {REDIRECT_URI}. Waiting for authorization code...")
            deadline = time.monotonic() + CALLBACK_TIMEOUT_SECONDS
            while not CALLBACK_CODE and time.monotonic() < deadline:
                httpd.handle_request()
    except OSError as e:
        raise ValueError(f"Error starting OAuth callback server: {e}") from e
    if not CALLBACK_CODE:
        raise ValueError("Authorization code was not received")
    if CALLBACK_STATE != expected_state:
        raise ValueError("OAuth state mismatch")
    return CALLBACK_CODE


async def exchange_code_for_token(code: str, code_verifier: str) -> Dict:
    url = "https://myanimelist.net/v1/oauth2/token"
    payload = {
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise httpx.HTTPStatusError(
                safe_error(f"Error getting token: {e.response.status_code} {e.response.reason_phrase}"),
                request=e.request,
                response=e.response,
            ) from e
        return response.json()


async def refresh_access_token(refresh_token: str) -> Dict:
    url = "https://myanimelist.net/v1/oauth2/token"
    payload = {
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise httpx.HTTPStatusError(
                safe_error(f"Error refreshing token: {e.response.status_code} {e.response.reason_phrase}"),
                request=e.request,
                response=e.response,
            ) from e
        return response.json()


def _set_memory(tokens: StoredTokens) -> None:
    global _access_token, _refresh_token, _expires_at
    _access_token = tokens.access_token
    _refresh_token = tokens.refresh_token
    _expires_at = tokens.expires_at


async def get_mal_access_token() -> str:
    current_time = time.time()
    if _access_token and _expires_at and current_time < _expires_at - 60:
        return _access_token

    stored = TOKEN_STORE.load()
    if stored and stored.is_valid:
        _set_memory(stored)
        return stored.access_token

    refresh_token = _refresh_token or (stored.refresh_token if stored else None)
    if refresh_token:
        try:
            data = await refresh_access_token(refresh_token)
            refreshed = StoredTokens.from_token_response(data, now=current_time, existing_refresh_token=refresh_token)
            TOKEN_STORE.save(refreshed)
            _set_memory(refreshed)
            return refreshed.access_token
        except httpx.HTTPStatusError:
            print("Couldn't refresh the MAL token. Starting a new OAuth flow...")

    auth_url, code_verifier, state = await get_authorization_url()
    print(f"Open this URL in your browser to authorize MyAnimeList access:\n{auth_url}")
    webbrowser.open(auth_url)
    code = await capture_authorization_code(state)
    data = await exchange_code_for_token(code, code_verifier)
    tokens = StoredTokens.from_token_response(data, now=current_time)
    TOKEN_STORE.save(tokens)
    _set_memory(tokens)
    return tokens.access_token


def get_auth_status() -> dict:
    stored = TOKEN_STORE.load()
    if not stored:
        return {"authenticated": False, "token_path": str(TOKEN_STORE.path)}
    return {
        "authenticated": stored.is_valid,
        "expires_at": stored.expires_at,
        "has_refresh_token": bool(stored.refresh_token),
        "token_path": str(TOKEN_STORE.path),
    }


def revoke_auth() -> dict:
    global _access_token, _refresh_token, _expires_at
    TOKEN_STORE.clear()
    _access_token = None
    _refresh_token = None
    _expires_at = None
    return {"authenticated": False, "message": "Stored MyAnimeList tokens cleared"}
