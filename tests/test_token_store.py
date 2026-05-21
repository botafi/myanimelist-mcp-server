import json
import os
import stat
import time
from pathlib import Path

from utils.token_store import TokenStore, StoredTokens


def test_token_store_round_trip_and_uses_private_file_mode(tmp_path: Path):
    path = tmp_path / "mal_tokens.json"
    store = TokenStore(path)

    tokens = StoredTokens(
        access_token="access-123",
        refresh_token="refresh-456",
        expires_at=1234567890.0,
        token_type="Bearer",
    )

    store.save(tokens)

    assert store.load() == tokens
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_token_store_returns_none_for_missing_or_invalid_file(tmp_path: Path):
    store = TokenStore(tmp_path / "missing.json")
    assert store.load() is None

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json")
    assert TokenStore(invalid).load() is None


def test_token_store_can_clear_tokens(tmp_path: Path):
    path = tmp_path / "mal_tokens.json"
    store = TokenStore(path)
    store.save(StoredTokens("access", "refresh", time.time() + 3600))

    store.clear()

    assert not path.exists()
    assert store.load() is None


def test_token_store_default_path_uses_hermes_home(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    monkeypatch.delenv("MAL_TOKEN_STORAGE_PATH", raising=False)

    path = TokenStore.default_path()

    assert path == tmp_path / "hermes" / "secrets" / "mal_tokens.json"


def test_token_store_env_path_overrides_default(monkeypatch, tmp_path: Path):
    explicit = tmp_path / "custom" / "tokens.json"
    monkeypatch.setenv("MAL_TOKEN_STORAGE_PATH", str(explicit))

    assert TokenStore.default_path() == explicit
