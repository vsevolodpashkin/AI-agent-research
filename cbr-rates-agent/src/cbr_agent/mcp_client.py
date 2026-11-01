"""Подключение к MCP-серверу CBR через langchain-mcp-adapters (stdio transport)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession

from cbr_agent.config import Settings

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "cbr"


def build_mcp_client(settings: Settings) -> MultiServerMCPClient:
    """Создаёт клиент MultiServerMCPClient, который ленится поднимать stdio-подпроцесс.

    Сам по себе клиент подключение не открывает — это произойдёт в ``mcp_session``.
    """
    return MultiServerMCPClient(
        {
            MCP_SERVER_NAME: {
                "transport": "stdio",
                "command": settings.mcp_cbr_command,
                "args": list(settings.mcp_cbr_args),
            }
        }
    )


@asynccontextmanager
async def mcp_session(
    client: MultiServerMCPClient, server_name: str = MCP_SERVER_NAME
) -> AsyncIterator[ClientSession]:
    """Открывает сессию с MCP-сервером на время жизни приложения.

    Держит stdio-подпроцесс запущенным, чтобы каждый вызов тула не стартовал новый процесс.
    """
    async with client.session(server_name) as session:
        logger.info("MCP session '%s' initialized", server_name)
        yield session


async def load_cbr_tools(session: ClientSession) -> list[BaseTool]:
    """Загружает инструменты MCP-сервера как LangChain BaseTool."""
    tools = await load_mcp_tools(session, server_name=MCP_SERVER_NAME, tool_name_prefix=True)
    logger.info("loaded %d tools from MCP: %s", len(tools), [t.name for t in tools])
    return tools
