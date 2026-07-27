from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import http.server
import logging
import os
import secrets
import socketserver
import time
import urllib.parse
from typing import Any

import httpx
from dotenv import load_dotenv

from utils.token_store import StoredTokens, TokenStore

load_dotenv()

LOGGER = logging.getLogger(__name__)

CLIENT_ID = os.getenv("MAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("MAL_CLIENT_SECRET")
REDIRECT_URI = os.getenv("MAL_REDIRECT_URI", "http://localhost:8080/callback")
CALLBACK_HOST = os.getenv("MAL_CALLBACK_HOST", "127.0.0.1")
CALLBACK_PORT = int(os.getenv("MAL_CALLBACK_PORT", "8080"))
CALLBACK_TIMEOUT_SECONDS = float(os.getenv("MAL_CALLBACK_TIMEOUT_SECONDS", "300"))
PKCE_METHOD = os.getenv("MAL_PKCE_METHOD", "plain").lower()

# Public globals used by the callback server and by tests that monkeypatch it.
CALLBACK_CODE: str | None = None
CALLBACK_STATE: str | None = None

_MAL_OAUTH_AUTH_URL = "https://myanimelist.net/v1/oauth2/authorize"
_MAL_OAUTH_TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"

# In-memory login state for the non-blocking OAuth flow.
_login_state: dict[str, Any] = {}


def _token_store() -> TokenStore:
    return TokenStore()


def _require_client_id() -> str:
    client_id = os.getenv("MAL_CLIENT_ID") or CLIENT_ID
    if not client_id:
        raise ValueError("MAL_CLIENT_ID is not configured")
    return client_id


def _require_client_secret() -> str:
    client_secret = os.getenv("MAL_CLIENT_SECRET") or CLIENT_SECRET
    if not client_secret:
        raise ValueError("MAL_CLIENT_SECRET is not configured")
    return client_secret


def _pkce_method() -> str:
    method = (os.getenv("MAL_PKCE_METHOD") or PKCE_METHOD).lower()
    if method not in {"plain", "s256"}:
        raise ValueError("MAL_PKCE_METHOD must be either 'plain' or 'S256'")
    return method


def _generate_pkce() -> tuple[str, str, str]:
    """Return (code_verifier, code_challenge, code_challenge_method)."""
    verifier = secrets.token_urlsafe(64)
    method = _pkce_method()
    if method == "plain":
        return verifier, verifier, "plain"

    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge, "S256"


def _authorization_url(state: str, code_challenge: str, code_challenge_method: str) -> str:
    params = {
        "response_type": "code",
        "client_id": _require_client_id(),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "redirect_uri": REDIRECT_URI,
    }
    return f"{_MAL_OAUTH_AUTH_URL}?{urllib.parse.urlencode(params)}"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        # Reduce request logging noise; sensitive query params are never logged.
        pass

    def _send_html(self, status: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        global CALLBACK_CODE, CALLBACK_STATE

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self._send_html(404, "<h1>Not found</h1>")
            return

        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        error = qs.get("error", [None])[0]

        if error:
            self._send_html(400, f"<h1>Authorization error</h1><p>{html.escape(error)}</p>")
            return

        if code and state:
            CALLBACK_CODE = code
            CALLBACK_STATE = state
            self._send_html(
                200,
                "<h1>Authorization received</h1><p>You can close this window.</p>",
            )
            return

        # Empty probe request (e.g., from a browser preflight or health check).
        self._send_html(200, "<h1>Waiting for authorization…</h1>")


def capture_authorization_code(expected_state: str) -> str | None:
    """Run a one-shot HTTP callback server until the expected state arrives or timeout."""
    global CALLBACK_CODE, CALLBACK_STATE
    CALLBACK_CODE = None
    CALLBACK_STATE = None

    server_address = (CALLBACK_HOST, CALLBACK_PORT)
    deadline = time.monotonic() + CALLBACK_TIMEOUT_SECONDS
    server_cls = socketserver.TCPServer
    server_cls.allow_reuse_address = True

    with server_cls(server_address, _CallbackHandler) as server:
        server.timeout = 1.0
        while time.monotonic() < deadline:
            server.handle_request()
            if CALLBACK_CODE and CALLBACK_STATE == expected_state:
                return CALLBACK_CODE
            if CALLBACK_CODE and CALLBACK_STATE != expected_state:
                LOGGER.warning("OAuth state mismatch; continuing to wait")
                CALLBACK_CODE = None
                CALLBACK_STATE = None
        return None


async def _exchange_code_for_token(code: str, code_verifier: str) -> StoredTokens:
    """Exchange an authorization code for tokens."""
    data = {
        "grant_type": "authorization_code",
        "client_id": _require_client_id(),
        "client_secret": _require_client_secret(),
        "code": code,
        "code_verifier": code_verifier,
        "redirect_uri": REDIRECT_URI,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_MAL_OAUTH_TOKEN_URL, data=data)
        response.raise_for_status()
        payload = response.json()
    return StoredTokens.from_token_response(payload)


async def _refresh_tokens(refresh_token: str) -> StoredTokens:
    data = {
        "grant_type": "refresh_token",
        "client_id": _require_client_id(),
        "client_secret": _require_client_secret(),
        "refresh_token": refresh_token,
    }
    existing = _token_store().load()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(_MAL_OAUTH_TOKEN_URL, data=data)
        response.raise_for_status()
        payload = response.json()
    tokens = StoredTokens.from_token_response(payload, existing_refresh_token=refresh_token)
    _token_store().save(tokens)
    return tokens


_REFRESH_LOCK = asyncio.Lock()


async def get_auth_status() -> dict[str, Any]:
    """Return non-sensitive auth status information, attempting a silent refresh if needed.

    When the access token is expired or near-expiry but a refresh token is available,
    this will attempt a silent token refresh. It never initiates interactive login.
    """
    store = _token_store()
    tokens = store.load()

    if tokens is not None and tokens.is_valid:
        return {
            "authenticated": True,
            "provider": "myanimelist",
            "expires_at": tokens.expires_at,
            "token_path": str(store.path),
        }

    if tokens is not None and tokens.refresh_token:
        async with _REFRESH_LOCK:
            tokens = store.load()
            if tokens is not None and tokens.is_valid:
                return {
                    "authenticated": True,
                    "provider": "myanimelist",
                    "expires_at": tokens.expires_at,
                    "token_path": str(store.path),
                }
            if tokens is not None and tokens.refresh_token:
                try:
                    refreshed = await _refresh_tokens(tokens.refresh_token)
                    return {
                        "authenticated": True,
                        "provider": "myanimelist",
                        "expires_at": refreshed.expires_at,
                        "token_path": str(store.path),
                    }
                except Exception as exc:
                    LOGGER.warning("Silent refresh failed during auth status check: %s", exc)

    if tokens is None:
        return {
            "authenticated": False,
            "provider": "myanimelist",
            "reason": "no_stored_tokens",
            "token_path": str(store.path),
        }

    return {
        "authenticated": False,
        "provider": "myanimelist",
        "reason": "token_expired",
        "token_path": str(store.path),
    }


def revoke_auth() -> dict[str, Any]:
    """Clear stored tokens."""
    store = _token_store()
    store.clear()
    _login_state.clear()
    return {"authenticated": False, "provider": "myanimelist", "message": "Tokens revoked"}


async def get_mal_access_token() -> str:
    """Return a valid access token, refreshing if possible.

    Raises RuntimeError with a clear message when no token exists and refresh is not possible.
    """
    store = _token_store()
    tokens = store.load()

    if tokens is not None and tokens.is_valid:
        return tokens.access_token

    if tokens is not None and tokens.refresh_token:
        async with _REFRESH_LOCK:
            tokens = store.load()
            if tokens is not None and tokens.is_valid:
                return tokens.access_token
            if tokens is not None and tokens.refresh_token:
                try:
                    refreshed = await _refresh_tokens(tokens.refresh_token)
                    return refreshed.access_token
                except Exception as exc:
                    LOGGER.warning("Failed to refresh MAL token: %s", exc)

    raise RuntimeError(
        "No valid MyAnimeList access token available. "
        "Call the 'mal_auth_login' tool first to start OAuth authorization."
    )


async def _watch_login(state: str, verifier: str) -> None:
    """Background task: wait for callback, exchange code, save tokens."""
    try:
        code = await asyncio.to_thread(capture_authorization_code, state)
        if code is None:
            _login_state["error"] = "Authorization timed out or no callback received"
            return
        tokens = await _exchange_code_for_token(code, verifier)
        _token_store().save(tokens)
        _login_state["completed_at"] = time.time()
    except Exception as exc:
        LOGGER.exception("MAL login failed")
        _login_state["error"] = f"Login failed: {exc}"


def login_initiate() -> dict[str, Any]:
    """Start a non-blocking MyAnimeList OAuth login and return the authorization URL."""
    store = _token_store()
    tokens = store.load()
    if tokens is not None and tokens.is_valid:
        return {
            "status": "already_authenticated",
            "provider": "myanimelist",
            "authorization_url": None,
            "redirect_uri": REDIRECT_URI,
        }

    _require_client_id()
    _require_client_secret()

    existing_task = _login_state.get("task")
    if existing_task is not None and not existing_task.done():
        return {
            "status": "pending",
            "provider": "myanimelist",
            "authorization_url": _login_state.get("authorization_url"),
            "redirect_uri": REDIRECT_URI,
        }

    state = secrets.token_urlsafe(16)
    verifier, challenge, challenge_method = _generate_pkce()
    auth_url = _authorization_url(state, challenge, challenge_method)

    _login_state.clear()
    _login_state.update(
        {
            "state": state,
            "verifier": verifier,
            "code_challenge_method": challenge_method,
            "authorization_url": auth_url,
            "redirect_uri": REDIRECT_URI,
        }
    )

    # Start the callback watcher as a background asyncio task.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    task = loop.create_task(_watch_login(state, verifier))
    _login_state["task"] = task

    return {
        "status": "pending",
        "provider": "myanimelist",
        "authorization_url": auth_url,
        "redirect_uri": REDIRECT_URI,
    }


async def login_status() -> dict[str, Any]:
    """Check whether a login is pending, completed, or not authenticated."""
    tokens = _token_store().load()
    if tokens is not None and tokens.is_valid:
        return {
            "authenticated": True,
            "status": "authenticated",
            "provider": "myanimelist",
            "expires_at": tokens.expires_at,
        }

    task = _login_state.get("task")
    error = _login_state.get("error")

    if task is not None and not task.done():
        return {
            "authenticated": False,
            "status": "pending",
            "provider": "myanimelist",
            "authorization_url": _login_state.get("authorization_url"),
            "redirect_uri": _login_state.get("redirect_uri"),
        }

    if error:
        return {
            "authenticated": False,
            "status": "failed",
            "provider": "myanimelist",
            "error": error,
        }

    return {
        "authenticated": False,
        "status": "not_authenticated",
        "provider": "myanimelist",
    }
