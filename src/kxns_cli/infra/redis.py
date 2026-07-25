from __future__ import annotations

import asyncio
from typing import Any


class RedisRateLimiter:
    """Redis-backed rate limiter for scan job dispatch (Phase 2)."""

    def __init__(self, url: str = "redis://127.0.0.1:6379/0", max_slots: int = 8) -> None:
        self._url = url
        self._max_slots = max_slots
        self._client: Any = None

    async def connect(self) -> None:
        try:
            import redis.asyncio as redis

            self._client = redis.from_url(
                self._url,
                socket_connect_timeout=3,
                socket_timeout=5,
            )
            await asyncio.wait_for(self._client.ping(), timeout=5.0)
        except Exception:
            self._client = None

    async def acquire(self, key: str = "kxns:scan:slots", timeout: float = 30.0) -> bool:
        if self._client is None:
            return True
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                current = await asyncio.wait_for(self._client.incr(key), timeout=5.0)
            except (TimeoutError, Exception):
                self._client = None
                return True
            if current <= self._max_slots:
                return True
            try:
                await asyncio.wait_for(self._client.decr(key), timeout=5.0)
            except (TimeoutError, Exception):
                self._client = None
                return True
            await asyncio.sleep(0.2)
        return False

    async def release(self, key: str = "kxns:scan:slots") -> None:
        if self._client is None:
            return
        try:
            await asyncio.wait_for(self._client.decr(key), timeout=5.0)
        except (TimeoutError, Exception):
            self._client = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
