import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, Mock, patch

from utils.mal_client import (
    MALAPIError,
    build_fields,
    clamp_limit,
    safe_error,
    api_error_payload,
    MALClientConfig,
    MALClient,
)


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


class TestApiErrorPayload:
    def test_mal_api_error_with_empty_payload(self):
        err = MALAPIError("MAL API returned an empty error", payload={"error": ""})
        result = api_error_payload(err)
        assert result["error"] == "MAL API returned an empty error"
        assert result["status_code"] == 200

    def test_mal_api_error_with_message(self):
        err = MALAPIError("MAL API returned an error: invalid season", payload={"error": "invalid season"})
        result = api_error_payload(err)
        assert result["error"] == "MAL API returned an error: invalid season"
        assert result["status_code"] == 200

    def test_mal_api_error_fallback_for_empty_str(self):
        err = MALAPIError("", payload={"error": ""})
        result = api_error_payload(err)
        assert result["error"] == "MALAPIError"
        assert result["status_code"] == 200

    def test_http_status_error_with_valid_reason(self):
        req = Mock()
        resp = Mock()
        resp.status_code = 404
        resp.reason_phrase = "Not Found"
        err = httpx.HTTPStatusError("msg", request=req, response=resp)
        result = api_error_payload(err)
        assert "MAL API error: 404 Not Found" in result["error"]
        assert result["status_code"] == 404

    def test_http_status_error_with_empty_reason(self):
        req = Mock()
        resp = Mock()
        resp.status_code = 400
        resp.reason_phrase = ""
        err = httpx.HTTPStatusError("msg", request=req, response=resp)
        result = api_error_payload(err)
        assert "MAL API error: 400" in result["error"]
        assert result["status_code"] == 400

    def test_generic_exception_fallback_for_empty_str(self):
        err = Exception("")
        result = api_error_payload(err)
        assert result["error"] == "Exception"

    def test_generic_exception_with_no_message(self):
        err = Exception()
        result = api_error_payload(err)
        assert result["error"] == "Exception"

    def test_value_error_with_message(self):
        err = ValueError("something went wrong")
        result = api_error_payload(err)
        assert result["error"] == "something went wrong"


class TestMALClientEmptyErrorDetection:
    def test_request_raises_on_empty_error_response(self, monkeypatch):
        monkeypatch.setenv("MAL_CLIENT_ID", "test-id")
        config = MALClientConfig(client_id="test-id")
        client = MALClient(config=config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"error":""}'
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={"error": ""})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.request = AsyncMock(return_value=mock_response)

        with patch("utils.mal_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(MALAPIError, match="MAL API returned an empty error"):
                asyncio.run(client.request("GET", "/anime/season/2026/summer", params={"limit": 10}))

    def test_request_raises_on_error_with_message(self, monkeypatch):
        monkeypatch.setenv("MAL_CLIENT_ID", "test-id")
        config = MALClientConfig(client_id="test-id")
        client = MALClient(config=config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"error":"invalid season","message":"details"}'
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={"error": "invalid season", "message": "details"})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.request = AsyncMock(return_value=mock_response)

        with patch("utils.mal_client.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(MALAPIError, match="MAL API returned an error: invalid season"):
                asyncio.run(client.request("GET", "/anime/season/2026/summer", params={"limit": 10}))

    def test_request_passes_through_valid_response(self, monkeypatch):
        monkeypatch.setenv("MAL_CLIENT_ID", "test-id")
        config = MALClientConfig(client_id="test-id")
        client = MALClient(config=config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"data":[{"node":{"id":1,"title":"Test"}}]}'
        mock_response.raise_for_status = Mock()
        mock_response.json = Mock(return_value={"data": [{"node": {"id": 1, "title": "Test"}}]})

        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.request = AsyncMock(return_value=mock_response)

        with patch("utils.mal_client.httpx.AsyncClient", return_value=mock_http):
            result = asyncio.run(client.request("GET", "/anime/season/2024/summer", params={"limit": 10}))
            assert result["data"][0]["node"]["title"] == "Test"
