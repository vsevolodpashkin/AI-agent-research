"""Smoke-тесты: проверяем, что модули импортируются и фабрики собираются.

Не требуют запущенного Redis/MCP — это быстрая проверка работоспособности кода.
"""

from __future__ import annotations

import importlib
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool


def test_imports() -> None:
    for module in [
        "cbr_agent",
        "cbr_agent.config",
        "cbr_agent.logging",
        "cbr_agent.cache",
        "cbr_agent.memory",
        "cbr_agent.llm",
        "cbr_agent.mcp_client",
        "cbr_agent.tools_cache",
        "cbr_agent.agent",
        "cbr_agent.api",
        "cbr_agent.main",
    ]:
        importlib.import_module(module)


def test_make_key_is_stable() -> None:
    from cbr_agent.cache import RedisCache

    a = RedisCache.make_key("ns", {"b": 1, "a": 2})
    b = RedisCache.make_key("ns", {"a": 2, "b": 1})
    assert a == b
    c = RedisCache.make_key("ns", {"a": 2, "b": 3})
    assert a != c


def test_extract_final_ai_message() -> None:
    from cbr_agent.agent import extract_final_ai_message

    msgs: list[Any] = [
        HumanMessage(content="hi"),
        AIMessage(content="", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
        ToolMessage(content="ok", tool_call_id="1"),
        AIMessage(content="final answer"),
    ]
    assert extract_final_ai_message(msgs) == "final answer"


def test_build_messages_for_turn() -> None:
    from cbr_agent.agent import build_messages_for_turn

    out = build_messages_for_turn(
        history=[HumanMessage(content="prev")],
        user_input="new",
        system_prompt=SystemMessage(content="sys"),
    )
    assert len(out) == 3
    assert out[0].content == "sys"
    assert out[1].content == "prev"
    assert isinstance(out[2], HumanMessage)


def test_tool_cache_hits_on_second_call() -> None:
    """Проверяем, что wrap_tool_with_cache действительно кэширует результат."""
    import fakeredis.aioredis

    import cbr_agent.cache as cache_mod
    from cbr_agent.cache import RedisCache
    from cbr_agent.tools_cache import wrap_tool_with_cache

    cache_mod.aioredis.from_url = (
        lambda url, **kw: fakeredis.aioredis.FakeRedis(decode_responses=kw.get("decode_responses", True))
    )

    calls = {"n": 0}

    @tool
    def add(a: int, b: int) -> int:
        """Складывает два числа."""
        calls["n"] += 1
        return a + b

    import asyncio

    async def go() -> None:
        cache = RedisCache("redis://fake", 60)
        wrapped = wrap_tool_with_cache(add, cache)
        r1 = await wrapped.ainvoke({"a": 2, "b": 3})
        r2 = await wrapped.ainvoke({"a": 2, "b": 3})
        r3 = await wrapped.ainvoke({"a": 2, "b": 4})
        await cache.close()
        assert r1 == 5
        assert r2 == 5
        assert r3 == 6
        # Вызов самой функции должен произойти только для двух уникальных пар аргументов.
        assert calls["n"] == 2

    asyncio.run(go())

