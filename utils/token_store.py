from __future__ import annotations

import json
import os
import stat
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StoredTokens:
    access_token: str
    refresh_token: str | None
    expires_at: float
    token_type: str = "Bearer"

    @property
    def is_valid(self) -> bool:
        return bool(self.access_token) and time.time() < self.expires_at - 60

    @classmethod
    def from_token_response(cls, data: dict[str, Any], now: float | None = None, existing_refresh_token: str | None = None) -> "StoredTokens":
        now = time.time() if now is None else now
        refresh_token = data.get("refresh_token") or existing_refresh_token
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at=now + float(data.get("expires_in", 0)),
            token_type=str(data.get("token_type", "Bearer")),
        )


class TokenStore:
    """Small JSON token store with private POSIX permissions.

    This intentionally avoids printing or logging token values. It is not encryption,
    but it prevents accidental world/group reads inside the runtime container.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else self.default_path()

    @staticmethod
    def default_path() -> Path:
        explicit = os.getenv("MAL_TOKEN_STORAGE_PATH")
        if explicit:
            return Path(explicit).expanduser()

        hermes_home = Path(os.getenv("HERMES_HOME", "~/.hermes")).expanduser()
        return hermes_home / "secrets" / "mal_tokens.json"

    def load(self) -> StoredTokens | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return StoredTokens(
                access_token=str(data["access_token"]),
                refresh_token=data.get("refresh_token"),
                expires_at=float(data["expires_at"]),
                token_type=str(data.get("token_type", "Bearer")),
            )
        except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def save(self, tokens: StoredTokens) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, stat.S_IRWXU)
        except PermissionError:
            pass

        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(asdict(tokens), indent=2), encoding="utf-8")
        try:
            os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)
        except PermissionError:
            pass
        tmp_path.replace(self.path)
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except PermissionError:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
