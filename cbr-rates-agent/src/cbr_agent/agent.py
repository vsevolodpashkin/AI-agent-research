"""LangGraph ReAct-агент поверх MCP-тулов и OpenAI-совместимого LLM."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from cbr_agent.cache import RedisCache
from cbr_agent.config import Settings
from cbr_agent.llm import build_llm
from cbr_agent.tools_cache import wrap_tool_with_cache

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_TEMPLATE = """\
Ты — ассистент по курсам валют и макроэкономике России. Данные предоставляются \
Центральным банком РФ (CBR) через MCP-инструменты.

Правила:
1. Если пользователь спрашивает о курсах валют, ключевой ставке или инфляции — \
ОБЯЗАТЕЛЬНО вызови соответствующий инструмент, а не придумывай числа.
2. Используй ISO-формат дат: YYYY-MM-DD.
3. Дата сегодня: {today}. Если пользователь говорит "сегодня" или "сейчас" — используй её.
4. Если инструмент вернул ошибку или пустые данные, честно сообщи об этом.
5. Отвечай кратко, на русском, с указанием источника (ЦБ РФ)."""


def build_system_prompt() -> SystemMessage:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    return SystemMessage(content=SYSTEM_PROMPT_TEMPLATE.format(today=today))


def create_agent(
    settings: Settings,
    tools: list[Any],
) -> CompiledStateGraph:
    """Создаёт скомпилированный LangGraph ReAct-агент."""
    llm = build_llm(settings)
    return create_react_agent(model=llm, tools=tools)


def wrap_cbr_tools_with_cache(tools: list[Any], cache: RedisCache) -> list[Any]:
    return [wrap_tool_with_cache(t, cache) for t in tools]


def extract_final_ai_message(messages: list[BaseMessage]) -> str:
    """Возвращает текст последнего AIMessage (финального ответа агента)."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            # content может быть list[dict] для мультимодальных ответов — склеиваем текстовые блоки
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif isinstance(block, str):
                    parts.append(block)
            if parts:
                return "\n".join(parts)
    return ""


def build_messages_for_turn(
    history: list[BaseMessage],
    user_input: str,
    system_prompt: SystemMessage,
) -> list[BaseMessage]:
    """Склеивает системный промпт, историю и новое сообщение пользователя."""
    return [system_prompt, *history, HumanMessage(content=user_input)]
