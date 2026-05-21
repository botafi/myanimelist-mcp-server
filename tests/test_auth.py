import asyncio
import socketserver

import utils.auth as auth


def test_callback_server_default_bind_host_is_loopback():
    assert auth.CALLBACK_HOST == "127.0.0.1"


def test_capture_authorization_code_binds_to_configured_host(monkeypatch):
    observed: dict[str, object] = {}

    class FakeServer:
        allow_reuse_address = False

        def __init__(self, address, handler):
            observed["address"] = address

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

    code = asyncio.run(auth.capture_authorization_code("expected"))

    assert code == "code"
    assert observed["address"] == ("127.0.0.1", 8080)
