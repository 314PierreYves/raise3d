"""Async client for r3monitor, the read-only HTTP bridge running on the printer.

r3monitor (see ``printer/r3monitor.py``) reads Klipper's Unix socket and serves:
    GET /status        summary JSON (state, progress, temperatures, ETA...)
    GET /raw           raw Klipper objects
    GET /snapshot.jpg  single camera frame (503 when the camera is unavailable)

There is no authentication and no write endpoint.
This module only depends on aiohttp so it can be used outside Home Assistant.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

REQUEST_TIMEOUT = 10
# r3monitor waits up to 8 s for a frame from MXCCameraServer.
SNAPSHOT_TIMEOUT = 15


class Raise3DError(Exception):
    """Base error for r3monitor."""


class Raise3DConnectionError(Raise3DError):
    """r3monitor could not be reached or returned an invalid answer."""


class Raise3DClient:
    """Minimal async client for one r3monitor instance."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int = 8090) -> None:
        self._session = session
        self.base_url = f"http://{host}:{port}"

    async def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"
        try:
            async with (
                asyncio.timeout(REQUEST_TIMEOUT),
                self._session.get(url) as resp,
            ):
                resp.raise_for_status()
                payload = await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError, ValueError) as err:
            raise Raise3DConnectionError(f"Error talking to {url}: {err}") from err
        if not isinstance(payload, dict):
            raise Raise3DConnectionError(f"Unexpected payload on {url}: {payload!r}")
        return payload

    async def get_status(self) -> dict[str, Any]:
        """Return the /status summary."""
        return await self._get_json("status")

    async def get_raw(self) -> dict[str, Any]:
        """Return the raw Klipper objects."""
        return await self._get_json("raw")

    async def get_snapshot(self) -> bytes | None:
        """Return a JPEG frame, or None when the camera is unavailable."""
        url = f"{self.base_url}/snapshot.jpg"
        try:
            async with (
                asyncio.timeout(SNAPSHOT_TIMEOUT),
                self._session.get(url) as resp,
            ):
                if resp.status != 200:
                    return None
                return await resp.read()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise Raise3DConnectionError(f"Error talking to {url}: {err}") from err
