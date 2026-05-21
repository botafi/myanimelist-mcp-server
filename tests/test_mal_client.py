import pytest

from utils.mal_client import build_fields, clamp_limit, safe_error, MALClientConfig


def test_build_fields_uses_default_when_none_or_empty():
    assert build_fields(None, ["id", "title"]) == "id,title"
    assert build_fields([], ["id", "title"]) == "id,title"


def test_build_fields_deduplicates_and_rejects_bad_values():
    assert build_fields(["id", "title", "id"], ["main_picture"]) == "id,title"

    with pytest.raises(ValueError, match="Invalid field"):
        build_fields(["id", "bad field"], ["title"])


def test_clamp_limit_respects_minimum_and_maximum():
    assert clamp_limit(0, maximum=500) == 1
    assert clamp_limit(999, maximum=500) == 500
    assert clamp_limit(42, maximum=500) == 42


def test_safe_error_does_not_include_response_body_or_secrets():
    err = safe_error("failure with token=abc123 and Authorization: Bearer secret-token")

    assert "abc123" not in err
    assert "secret-token" not in err
    assert "token=<redacted>" in err


def test_mal_client_config_requires_client_id_for_public_calls(monkeypatch):
    monkeypatch.delenv("MAL_CLIENT_ID", raising=False)

    with pytest.raises(ValueError, match="MAL_CLIENT_ID"):
        MALClientConfig.from_env(require_client_id=True)
