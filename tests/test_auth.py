import socketserver
import urllib.parse

import utils.auth as auth


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
