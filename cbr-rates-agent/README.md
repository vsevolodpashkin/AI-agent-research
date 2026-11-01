# CBR Rates Agent

Минимальный рабочий AI-агент на **Python 3.11+** для получения курсов валют, ключевой ставки и инфляции **Центрального банка РФ** через [MCP-сервер `atomno-mcp-cbr-rates`](https://github.com/atomno-mcp/mcp-cbr-rates).

## Стек

| Слой             | Технология                                                  |
| ---------------- | ----------------------------------------------------------- |
| Агентский фрейм  | **LangChain + LangGraph** (`create_react_agent`)            |
| MCP-интеграция   | `langchain-mcp-adapters` (`MultiServerMCPClient`, stdio)    |
| LLM              | **OpenAI-совместимый** (Groq / Together / vLLM / OpenAI)    |
| Хранилище        | **Redis** (кэш ответов MCP + история диалогов)             |
| API              | **FastAPI** + Uvicorn                                       |
| Конфиг           | `pydantic-settings` + `.env`                                |
| Сборка           | `pyproject.toml` + `uv`                                    |

## Архитектура

```
┌──────────┐    POST /chat    ┌──────────────┐
│  Client  │ ───────────────► │   FastAPI    │
└──────────┘                  │  /chat       │
                              └──────┬───────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
     ┌────────────────┐    ┌─────────────────┐    ┌─────────────────┐
     │  Redis         │    │  LangGraph      │    │  LLM (OpenAI-   │
     │  • кэш MCP     │    │  ReAct-agent    │───►│  совместимый)   │
     │  • история     │◄───┤  (create_react_ │◄───│  base_url       │
     │    диалогов    │    │   agent)        │    └─────────────────┘
     └────────────────┘    └────────┬────────┘
                                     │ tools (cached)
                                     ▼
                          ┌─────────────────────┐
                          │ MCP stdio subprocess│
                          │ atomno-mcp-cbr-rates│
                          │ (get_rate, history, │
                          │  key_rate, inflation│
                          │  statistics)        │
                          └─────────────────────┘
```

**Поток запроса `/chat`:**

1. Загрузить историю диалога из Redis по `session_id`.
2. Собрать сообщения: `[system, ...history, HumanMessage(user_input)]`.
3. Вызвать `agent.ainvoke({"messages": ...})` — LangGraph запускает ReAct-цикл.
4. При вызове любого MCP-тула сначала проверяется Redis-кэш, при miss — вызов stdio-подпроцесса MCP, результат кэшируется.
5. Финальный ответ + ввод пользователя сохраняются в историю Redis.

## Структура проекта

```
cbr-rates-agent/
├── pyproject.toml
├── docker-compose.yml          # Redis-сервис
├── .env.example
├── src/cbr_agent/
│   ├── config.py               # pydantic-settings
│   ├── logging.py              # настройка логирования
│   ├── cache.py                # RedisCache (TTL, sha256-ключи)
│   ├── memory.py               # RedisChatMessageHistory
│   ├── llm.py                  # ChatOpenAI с custom base_url
│   ├── mcp_client.py           # MultiServerMCPClient (stdio)
│   ├── tools_cache.py          # обёртка тулов с кэшем
│   ├── agent.py                # create_react_agent + helpers
│   ├── api.py                  # FastAPI: /chat, /health, lifespan
│   └── main.py                 # uvicorn entry point
└── tests/test_smoke.py
```

## Подготовка

### 1. Установить MCP-сервер CBR (отдельный пакет, ставится в системный PATH)

```bash
# Вариант A: uv
uv tool install atomno-mcp-cbr-rates

# Вариант B: pipx
pipx install atomno-mcp-cbr-rates

# Проверка
atomno-mcp-cbr-rates --help
```

### 2. Поднять Redis

```bash
docker compose up -d redis
```

### 3. Установить зависимости проекта

Требуется [uv](https://docs.astral.sh/uv/) (>= 0.4).

```bash
cd cbr-rates-agent
uv sync
```

### 4. Сконфигурировать переменные окружения

```bash
cp .env.example .env
# отредактируйте .env:
#   OPENAI_API_KEY     — ключ провайдера
#   OPENAI_BASE_URL    — например, https://api.groq.com/openai/v1
#   OPENAI_MODEL       — например, llama-3.3-70b-versatile
```

## Запуск

```bash
uv run cbr-agent
# или
uv run python -m cbr_agent.main
```

Сервер стартует на `http://0.0.0.0:8000` (настраивается через `APP_HOST` / `APP_PORT`).

## Использование API

### Проверка здоровья

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "redis": true,
  "mcp_loaded": true,
  "tools": ["cbr_get_rate", "cbr_history_rates", "cbr_key_rate", "cbr_inflation", "cbr_statistics"]
}
```

### Диалог с агентом

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-1",
    "message": "Какой сейчас курс доллара и сколько длится ключевая ставка?"
  }'
```

```json
{
  "session_id": "user-1",
  "response": "По данным ЦБ РФ на сегодня, курс доллара — …\nКлючевая ставка — …% годовых.",
  "tool_calls": ["cbr_get_rate", "cbr_key_rate"]
}
```

Продолжение диалога в той же сессии — бот помнит контекст:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"user-1","message":"А инфляция за последний год?"}'
```

## Тесты

```bash
uv run pytest
```

## Лицензия

MIT.
