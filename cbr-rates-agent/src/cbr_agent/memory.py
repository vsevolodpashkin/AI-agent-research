"""Память диалогов поверх Redis (RedisChatMessageHistory)."""

from __future__ import annotations

import logging

from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory

from cbr_agent.config import Settings

logger = logging.getLogger(__name__)


def make_history(settings: Settings, session_id: str) -> BaseChatMessageHistory:
    """Возвращает объект истории сообщений для конкретной сессии.

    TTL обнуляет сессию, если она не активна указанное число секунд.
    """
    if not session_id or not session_id.strip():
        msg = "session_id must be non-empty"
        raise ValueError(msg)

    logger.debug("opening chat history for session_id=%s", session_id)
    return RedisChatMessageHistory(
        session_id=session_id,
        url=settings.redis_url,
        ttl=settings.session_ttl_seconds,
    )
