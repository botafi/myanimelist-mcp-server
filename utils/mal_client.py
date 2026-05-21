from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

import httpx

MAL_API_URL = "https://api.myanimelist.net/v2"

_SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE), "Bearer <redacted>"),
    (re.compile(r"token=([^\s&]+)", re.IGNORECASE), "token=<redacted>"),
    (re.compile(r"refresh_token=([^\s&]+)", re.IGNORECASE), "refresh_token=<redacted>"),
    (re.compile(r"access_token=([^\s&]+)", re.IGNORECASE), "access_token=<redacted>"),
]

_FIELD_RE = re.compile(r"^[A-Za-z0-9_,.]+$")


def safe_error(message: str) -> str:
    clean = message
    for pattern, repl in _SECRET_PATTERNS:
        clean = pattern.sub(repl, clean)
    return clean


def clamp_limit(limit: int, maximum: int = 100) -> int:
    return max(1, min(int(limit), maximum))


def build_fields(fields: Iterable[str] | None, default: Iterable[str]) -> str:
    selected = list(fields or default)
    deduped: list[str] = []
    for field in selected:
        field = str(field).strip()
        if not field:
            continue
        if not _FIELD_RE.match(field):
            raise ValueError(f"Invalid field name: {field}")
        if field not in deduped:
            deduped.append(field)
    if not deduped:
        deduped = list(default)
    return ",".join(deduped)


@dataclass(frozen=True)
class MALClientConfig:
    client_id: str | None
    api_url: str = MAL_API_URL
    rate_limit_delay: float = 0.35

    @classmethod
    def from_env(cls, require_client_id: bool = False) -> "MALClientConfig":
        client_id = os.getenv("MAL_CLIENT_ID")
        if require_client_id and not client_id:
            raise ValueError("MAL_CLIENT_ID is required for MyAnimeList API calls")
        return cls(
            client_id=client_id,
            api_url=os.getenv("MAL_API_URL", MAL_API_URL),
            rate_limit_delay=float(os.getenv("MAL_RATE_LIMIT_DELAY", "0.35")),
        )


class MALClient:
    def __init__(self, config: MALClientConfig | None = None):
        self.config = config or MALClientConfig.from_env(require_client_id=True)
        self._last_request_at = 0.0

    async def _wait_for_slot(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.config.rate_limit_delay:
            await asyncio.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_at = time.monotonic()

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        token: str | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._wait_for_slot()
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif self.config.client_id:
            headers["X-MAL-CLIENT-ID"] = self.config.client_id
        else:
            raise ValueError("MAL_CLIENT_ID is required for unauthenticated API calls")

        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                f"{self.config.api_url}{endpoint}",
                headers=headers,
                params=params,
                data=data,
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return {"ok": True}
            return response.json()

    async def get_public(self, endpoint: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("GET", endpoint, params=params)

    async def get_authed(self, endpoint: str, token: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("GET", endpoint, token=token, params=params)

    async def put_authed(self, endpoint: str, token: str, *, data: dict[str, Any]) -> dict[str, Any]:
        return await self.request("PUT", endpoint, token=token, data=data)

    async def delete_authed(self, endpoint: str, token: str) -> dict[str, Any]:
        return await self.request("DELETE", endpoint, token=token)


def api_error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, httpx.HTTPStatusError):
        return {"error": safe_error(f"MAL API error: {error.response.status_code} {error.response.reason_phrase}"), "status_code": error.response.status_code}
    return {"error": safe_error(str(error))}
