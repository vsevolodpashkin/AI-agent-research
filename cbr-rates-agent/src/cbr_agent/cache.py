"""TTL-кэш в Redis для произвольных JSON-совместимых значений."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisCache:
    """Тонкая обёртка над redis.asyncio с TTL и хешированными ключами."""

    def __init__(self, url: str, ttl_seconds: int, namespace: str = "cache") -> None:
        self._client: aioredis.Redis = aioredis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds
        self._namespace = namespace

    @property
    def client(self) -> aioredis.Redis:
        return self._client

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("cache value for %s is not valid JSON, ignoring", key)
            return None

    async def set(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False, default=str)
        await self._client.set(key, payload, ex=self._ttl)

    async def ping(self) -> bool:
        return bool(await self._client.ping())

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def make_key(namespace: str, payload: dict[str, Any]) -> str:
        """Стабильный ключ: <namespace>:<sha256(canonical-json(payload))."""
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"{namespace}:{digest}"
