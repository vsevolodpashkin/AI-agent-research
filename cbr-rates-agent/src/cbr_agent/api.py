"""FastAPI-приложение: /chat endpoint, /health, lifespan-управление ресурсами."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, StringConstraints

from cbr_agent.agent import (
    build_messages_for_turn,
    build_system_prompt,
    create_agent,
    extract_final_ai_message,
    wrap_cbr_tools_with_cache,
)
from cbr_agent.cache import RedisCache
from cbr_agent.config import Settings, get_settings
from cbr_agent.logging import setup_logging
from cbr_agent.mcp_client import build_mcp_client, load_cbr_tools, mcp_session
from cbr_agent.memory import make_history

logger = logging.getLogger(__name__)


SessionId = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[\w\-:.]+$")]


class ChatRequest(BaseModel):
    session_id: SessionId = Field(..., description="Идентификатор сессии диалога")
    message: Annotated[str, StringConstraints(min_length=1, max_length=4096)] = Field(
        ..., description="Сообщение пользователя"
    )


class ChatResponse(BaseModel):
    session_id: SessionId
    response: str
    tool_calls: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    redis: bool
    mcp_loaded: bool
    tools: list[str] = Field(default_factory=list)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Фабрика приложения (нужно для тестов и для запуска)."""
    cfg = settings or get_settings()
    setup_logging(cfg.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # --- Startup ---
        cache = RedisCache(cfg.redis_url, cfg.cache_ttl_seconds)
        if not await cache.ping():
            msg = f"Redis at {cfg.redis_url} is not reachable"
            raise RuntimeError(msg)
        logger.info("Redis connected: %s", cfg.redis_url)

        mcp_client = build_mcp_client(cfg)
        async with mcp_session(mcp_client) as session:
            base_tools = await load_cbr_tools(session)
            cached_tools = wrap_cbr_tools_with_cache(base_tools, cache)
            agent = create_agent(cfg, cached_tools)

            app.state.settings = cfg
            app.state.cache = cache
            app.state.agent = agent
            app.state.tools = cached_tools
            logger.info("application ready: %d cached tools", len(cached_tools))

            try:
                yield
            finally:
                logger.info("shutting down")
                await cache.close()

    app = FastAPI(
        title="CBR Rates Agent",
        version="0.1.0",
        description="AI-агент для получения курсов валют ЦБ РФ через MCP",
        lifespan=lifespan,
    )

    register_routes(app)
    return app


def register_routes(app: FastAPI) -> None:
    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        cache: RedisCache = request.app.state.cache
        redis_ok = False
        try:
            redis_ok = await cache.ping()
        except Exception:
            logger.exception("redis ping failed")
        tools: list[str] = [t.name for t in getattr(request.app.state, "tools", [])]
        return HealthResponse(
            status="ok" if redis_ok else "degraded",
            redis=redis_ok,
            mcp_loaded=bool(tools),
            tools=tools,
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: Request, body: ChatRequest) -> ChatResponse:
        agent = getattr(request.app.state, "agent", None)
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="agent is not initialized",
            )

        history_store = make_history(request.app.state.settings, body.session_id)
        history_messages = list(history_store.messages)

        messages = build_messages_for_turn(
            history=history_messages,
            user_input=body.message,
            system_prompt=build_system_prompt(),
        )

        try:
            result = await agent.ainvoke({"messages": messages})
        except Exception:
            logger.exception("agent invocation failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="LLM or MCP call failed",
            ) from None

        new_messages = result.get("messages", [])
        answer = extract_final_ai_message(new_messages)

        tool_call_names: list[str] = []
        for m in new_messages:
            tc = getattr(m, "tool_calls", None)
            if tc:
                for call in tc:
                    name = call.get("name") if isinstance(call, dict) else None
                    if name:
                        tool_call_names.append(name)

        # Сохраняем в историю: ввод пользователя + финальный ответ агента.
        history_store.add_user_message(body.message)
        history_store.add_ai_message(answer)

        return ChatResponse(
            session_id=body.session_id,
            response=answer,
            tool_calls=tool_call_names,
        )
