import asyncio
import socketserver
import time
import urllib.parse
from unittest.mock import AsyncMock, Mock

import pytest

import utils.auth as auth
from utils.token_store import StoredTokens


def test_capture_authorization_code_binds_to_configured_host(monkeypatch):
    observed: dict[str, object] = {}

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, address, handler):
            observed["address"] = address
            self.timeout = None

        def __enter__(self):
            auth.CALLBACK_CODE = "code"
            auth.CALLBACK_STATE = "expected"
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def handle_request(self):
            return None

    monkeypatch.setattr(socketserver, "TCPServer", FakeServer)
    monkeypatch.setattr(auth, "CALLBACK_HOST", "127.0.0.1")
    monkeypatch.setattr(auth, "CALLBACK_PORT", 8080)

    code = auth.capture_authorization_code("expected")

    assert code == "code"
    assert observed["address"] == ("127.0.0.1", 8080)


def test_capture_authorization_code_ignores_empty_probe_requests(monkeypatch):
    calls = {"count": 0}

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, address, handler):
            self.timeout = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def handle_request(self):
            calls["count"] += 1
            if calls["count"] == 2:
                auth.CALLBACK_CODE = "code"
                auth.CALLBACK_STATE = "expected"

    monkeypatch.setattr(socketserver, "TCPServer", FakeServer)
    monkeypatch.setattr(auth, "CALLBACK_TIMEOUT_SECONDS", 30)

    code = auth.capture_authorization_code("expected")

    assert code == "code"
    assert calls["count"] == 2


def test_generate_pkce_defaults_to_plain_for_myanimelist(monkeypatch):
    monkeypatch.delenv("MAL_PKCE_METHOD", raising=False)
    monkeypatch.setattr(auth, "PKCE_METHOD", "plain")

    verifier, challenge, method = auth._generate_pkce()

    assert verifier == challenge
    assert method == "plain"


def test_authorization_url_uses_configured_pkce_method(monkeypatch):
    monkeypatch.setenv("MAL_CLIENT_ID", "client-id")
    monkeypatch.setattr(auth, "REDIRECT_URI", "http://localhost:8080/callback")

    url = auth._authorization_url("state", "challenge", "plain")
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)

    assert params["client_id"] == ["client-id"]
    assert params["state"] == ["state"]
    assert params["code_challenge"] == ["challenge"]
    assert params["code_challenge_method"] == ["plain"]
    assert params["redirect_uri"] == ["http://localhost:8080/callback"]


# ---------------------------------------------------------------------------
# Silent refresh tests for get_auth_status
# ---------------------------------------------------------------------------


def test_get_auth_status_valid_token_returns_authenticated(monkeypatch, tmp_path):
    now = time.time()
    tokens = StoredTokens(access_token="access", refresh_token="refresh", expires_at=now + 3600)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(tokens)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is True
    assert result["provider"] == "myanimelist"
    assert result["expires_at"] == pytest.approx(now + 3600)
    assert "token_path" in result


def test_get_auth_status_expired_token_refreshes_and_returns_authenticated(monkeypatch, tmp_path):
    now = time.time()
    expired_tokens = StoredTokens(access_token="old-access", refresh_token="old-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired_tokens)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="new-access", refresh_token="new-refresh", expires_at=now + 7200)

    async def fake_refresh(_refresh_token):
        store.save(refreshed)
        return refreshed

    mock_refresh = AsyncMock(side_effect=fake_refresh)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is True
    assert result["expires_at"] == pytest.approx(now + 7200)
    mock_refresh.assert_awaited_once_with("old-refresh")

    persisted = store.load()
    assert persisted is not None
    assert persisted.access_token == "new-access"
    assert persisted.refresh_token == "new-refresh"


def test_get_auth_status_near_expiry_token_refreshes(monkeypatch, tmp_path):
    now = time.time()
    near_expiry = StoredTokens(access_token="near-access", refresh_token="near-refresh", expires_at=now + 30)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(near_expiry)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="refreshed-access", refresh_token="refreshed-refresh", expires_at=now + 3600)
    mock_refresh = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is True
    mock_refresh.assert_awaited_once()


def test_get_auth_status_no_stored_tokens_returns_unauthenticated(monkeypatch, tmp_path):
    store = auth.TokenStore(tmp_path / "nonexistent.json")
    monkeypatch.setattr(auth, "_token_store", lambda: store)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is False
    assert result["reason"] == "no_stored_tokens"


def test_get_auth_status_refresh_failure_returns_unauthenticated(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old", refresh_token="bad-refresh", expires_at=now - 100)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    mock_refresh = AsyncMock(side_effect=Exception("refresh rejected"))
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is False
    assert "token_path" in result
    assert "access_token" not in result
    assert "refresh_token" not in result
    mock_refresh.assert_awaited_once()


def test_get_auth_status_expired_no_refresh_token_returns_unauthenticated(monkeypatch, tmp_path):
    now = time.time()
    expired_no_refresh = StoredTokens(access_token="old", refresh_token=None, expires_at=now - 100)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired_no_refresh)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    mock_refresh = AsyncMock()
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is False
    assert result["reason"] == "token_expired"
    mock_refresh.assert_not_awaited()


def test_get_auth_status_does_not_invoke_mal_auth_login(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old", refresh_token="old-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="new", refresh_token="new-refresh", expires_at=now + 3600)
    mock_refresh = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    login_called = Mock()
    monkeypatch.setattr(auth, "login_initiate", login_called)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is True
    login_called.assert_not_called()


def test_get_auth_status_refresh_token_rotation_persisted(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old", refresh_token="rotating-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    rotated = StoredTokens(access_token="rotated-access", refresh_token="rotated-refresh", expires_at=now + 3600)

    async def fake_refresh(_refresh_token):
        store.save(rotated)
        return rotated

    mock_refresh = AsyncMock(side_effect=fake_refresh)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is True

    persisted = store.load()
    assert persisted is not None
    assert persisted.access_token == "rotated-access"
    assert persisted.refresh_token == "rotated-refresh"


def test_get_auth_status_does_not_expose_token_secrets_on_refresh_failure(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="secret-access", refresh_token="secret-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    mock_refresh = AsyncMock(side_effect=Exception("invalid_grant"))
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_auth_status())

    assert result["authenticated"] is False
    assert "access_token" not in result
    assert "refresh_token" not in result
    assert "secret-access" not in str(result)
    assert "secret-refresh" not in str(result)
    assert "Bearer" not in str(result)


# ---------------------------------------------------------------------------
# get_mal_access_token tests
# ---------------------------------------------------------------------------


def test_get_mal_access_token_valid_returns_token(monkeypatch, tmp_path):
    now = time.time()
    tokens = StoredTokens(access_token="access", refresh_token="refresh", expires_at=now + 3600)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(tokens)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    result = asyncio.run(auth.get_mal_access_token())

    assert result == "access"


def test_get_mal_access_token_expired_refreshes_and_returns_token(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old-access", refresh_token="old-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="new-access", refresh_token="new-refresh", expires_at=now + 7200)

    async def fake_refresh(_refresh_token):
        store.save(refreshed)
        return refreshed

    mock_refresh = AsyncMock(side_effect=fake_refresh)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_mal_access_token())

    assert result == "new-access"
    mock_refresh.assert_awaited_once_with("old-refresh")


def test_get_mal_access_token_near_expiry_refreshes(monkeypatch, tmp_path):
    now = time.time()
    near_expiry = StoredTokens(access_token="near-access", refresh_token="near-refresh", expires_at=now + 30)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(near_expiry)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="refreshed-access", refresh_token="refreshed-refresh", expires_at=now + 3600)
    mock_refresh = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    result = asyncio.run(auth.get_mal_access_token())

    assert result == "refreshed-access"
    mock_refresh.assert_awaited_once()


def test_get_mal_access_token_no_stored_tokens_raises(monkeypatch, tmp_path):
    store = auth.TokenStore(tmp_path / "nonexistent.json")
    monkeypatch.setattr(auth, "_token_store", lambda: store)

    with pytest.raises(RuntimeError, match="mal_auth_login"):
        asyncio.run(auth.get_mal_access_token())


def test_get_mal_access_token_expired_no_refresh_token_raises(monkeypatch, tmp_path):
    now = time.time()
    expired_no_refresh = StoredTokens(access_token="old", refresh_token=None, expires_at=now - 100)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired_no_refresh)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    with pytest.raises(RuntimeError, match="mal_auth_login"):
        asyncio.run(auth.get_mal_access_token())


def test_get_mal_access_token_refresh_failure_raises(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old", refresh_token="bad-refresh", expires_at=now - 100)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    mock_refresh = AsyncMock(side_effect=Exception("refresh rejected"))
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    with pytest.raises(RuntimeError, match="mal_auth_login"):
        asyncio.run(auth.get_mal_access_token())

    mock_refresh.assert_awaited_once()


def test_get_mal_access_token_uses_lock_and_double_check(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old", refresh_token="old-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="refreshed", refresh_token="new-refresh", expires_at=now + 3600)

    refresh_calls = 0

    async def fake_refresh(token):
        nonlocal refresh_calls
        refresh_calls += 1
        await asyncio.sleep(0.01)
        store.save(refreshed)
        return refreshed

    mock_refresh = AsyncMock(side_effect=fake_refresh)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    async def concurrent_call():
        auth._REFRESH_LOCK = asyncio.Lock()
        return await asyncio.gather(
            auth.get_mal_access_token(),
            auth.get_mal_access_token(),
        )

    results = asyncio.run(concurrent_call())

    assert results == ["refreshed", "refreshed"]
    assert refresh_calls == 1


def test_get_mal_access_token_does_not_invoke_mal_auth_login(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="old", refresh_token="old-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    refreshed = StoredTokens(access_token="new", refresh_token="new-refresh", expires_at=now + 3600)
    mock_refresh = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    login_called = Mock()
    monkeypatch.setattr(auth, "login_initiate", login_called)

    result = asyncio.run(auth.get_mal_access_token())

    assert result == "new"
    login_called.assert_not_called()


def test_get_mal_access_token_does_not_expose_secrets_on_failure(monkeypatch, tmp_path):
    now = time.time()
    expired = StoredTokens(access_token="secret-access", refresh_token="secret-refresh", expires_at=now - 10)
    token_path = tmp_path / "mal_tokens.json"

    store = auth.TokenStore(token_path)
    store.save(expired)

    monkeypatch.setattr(auth, "_token_store", lambda: store)

    mock_refresh = AsyncMock(side_effect=Exception("invalid_grant"))
    monkeypatch.setattr(auth, "_refresh_tokens", mock_refresh)

    with pytest.raises(RuntimeError) as excinfo:
        asyncio.run(auth.get_mal_access_token())

    msg = str(excinfo.value)
    assert "secret-access" not in msg
    assert "secret-refresh" not in msg
    assert "Bearer" not in msg
