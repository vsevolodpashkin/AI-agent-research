"""Обёртка для LangChain-тулов с прозрачным Redis-кэшированием."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from cbr_agent.cache import RedisCache

logger = logging.getLogger(__name__)


def wrap_tool_with_cache(tool: BaseTool, cache: RedisCache) -> BaseTool:
    """Возвращает новый StructuredTool, который кэширует результаты ``tool.ainvoke``.

    Ключ кэша: ``mcp:<tool_name>:<sha256(args)>``. TTL берётся из ``RedisCache._ttl``.
    """
    tool_name = tool.name
    namespace = f"mcp:{tool_name}"

    description = tool.description
    args_schema = tool.args_schema

    async def _cached_call(**kwargs: Any) -> Any:
        key = RedisCache.make_key(namespace, kwargs)
        cached = await cache.get(key)
        if cached is not None:
            logger.debug("cache HIT  %s key=%s", tool_name, key)
            return cached

        logger.debug("cache MISS %s key=%s", tool_name, key)
        result = await tool.ainvoke(kwargs)
        # Результат StructuredTool.ainvoke может быть строкой или dict'ом (с content/artifacts).
        # Для кэша достаточно JSON-сериализуемого представления.
        if isinstance(result, str):
            payload: Any = {"result": result}
        else:
            payload = result
        await cache.set(key, payload)
        return result

    return StructuredTool(
        name=tool_name,
        description=description or "",
        args_schema=args_schema,
        coroutine=_cached_call,
    )
