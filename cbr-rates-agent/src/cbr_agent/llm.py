"""Фабрика LLM: OpenAI-совместимый чат-клиент (Groq, Together, vLLM, OpenAI)."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from cbr_agent.config import Settings


def build_llm(settings: Settings) -> ChatOpenAI:
    """Создаёт ChatOpenAI с указанным base_url. Работает с любым OpenAI-совместимым API."""
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0,
    )
