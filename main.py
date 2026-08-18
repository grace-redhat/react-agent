import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field
from react_agent.agent import get_graph_closure
from react_agent.tools import MCP_SERVER_CONFIG
from react_agent.tracing import enable_tracing

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: str | None = None
    stream: bool = False


class HealthResponse(BaseModel):
    status: str
    agent_initialized: bool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    enable_tracing()

    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")

    if base_url and not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    mcp_client = None
    mcp_tools = []
    try:
        mcp_client = MultiServerMCPClient(MCP_SERVER_CONFIG)
        mcp_tools = await mcp_client.get_tools()
        logger.info("MCP tools loaded: %s", [t.name for t in mcp_tools])
    except Exception as e:
        logger.warning("MCP tools unavailable, starting without them: %s", e)

    agent_graph = get_graph_closure(model_id=model_id, base_url=base_url, mcp_tools=mcp_tools)

    app.state.agent_graph = agent_graph
    app.state.mcp_client = mcp_client

    yield

    if mcp_client is not None:
        await mcp_client.__aexit__(None, None, None)
    app.state.agent_graph = None
    app.state.mcp_client = None


app = FastAPI(
    title="LangGraph React Agent API",
    description="FastAPI service for LangGraph React Agent with OpenAI-compatible chat completions API.",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Chat", "description": "Chat completion operations"},
        {"name": "Health", "description": "Service health monitoring"},
    ],
)


def _auth_enabled() -> bool:
    return getenv("AUTH_ENABLED", "false").strip().lower() == "true"


def _configure_auth_middleware() -> None:
    if not _auth_enabled():
        return
    try:
        from agent_auth.middleware import SATokenAuthMiddleware
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "AUTH_ENABLED=true, but auth middleware dependencies are not installed. "
            "Run `uv sync --extra auth` to enable ServiceAccount token auth locally."
        ) from exc
    app.add_middleware(SATokenAuthMiddleware)


_configure_auth_middleware()


def _build_langchain_messages(messages: list[ChatMessage]) -> list[HumanMessage]:
    for msg in reversed(messages):
        if msg.role == "user":
            return [HumanMessage(content=msg.content)]
    raise ValueError("No user message found in messages list")


def _format_tool_call(tc) -> dict:
    return {
        "id": tc["id"],
        "type": "function",
        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
    }


def _build_context(messages: list) -> list[dict]:
    context = []
    for message in messages:
        if isinstance(message, HumanMessage):
            context.append({"role": "user", "content": message.content})
        elif isinstance(message, AIMessage):
            entry = {"role": "assistant", "content": message.content or ""}
            if message.tool_calls:
                entry["tool_calls"] = [_format_tool_call(tc) for tc in message.tool_calls]
            context.append(entry)
        elif isinstance(message, ToolMessage):
            context.append({
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "name": message.name,
                "content": message.content,
            })
    return context


def _make_completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:12]}"


@app.post("/chat/completions", summary="Create chat completion", tags=["Chat"])
async def chat_completions(request_body: ChatCompletionRequest, request: Request):
    agent_graph = request.app.state.agent_graph
    if agent_graph is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    langchain_messages = _build_langchain_messages(request_body.messages)
    model_id = request_body.model or getenv("MODEL_ID") or "model"

    if request_body.stream:
        return _handle_stream(agent_graph, langchain_messages, model_id)
    return await _handle_chat(agent_graph, langchain_messages, model_id)


async def _handle_chat(agent_graph, messages: list[HumanMessage], model_id: str):
    result = await agent_graph.ainvoke(
        {"messages": messages}, config={"recursion_limit": 10}
    )

    result_messages = result.get("messages", [])
    context = _build_context(result_messages)

    assistant_content = ""
    for message in reversed(result_messages):
        if isinstance(message, AIMessage) and message.content:
            assistant_content = message.content
            break

    return {
        "id": _make_completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": assistant_content},
            "finish_reason": "stop",
        }],
        "context": context,
    }


def _handle_stream(agent_graph, messages: list[HumanMessage], model_id: str) -> StreamingResponse:
    completion_id = _make_completion_id()
    created = int(time.time())

    def _chunk(delta, finish_reason=None):
        return "data: " + json.dumps({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_id,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }) + "\n\n"

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in agent_graph.astream_events(
                {"messages": messages},
                config={"recursion_limit": 10},
                version="v2",
            ):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content:
                        yield _chunk({"content": chunk.content})

                elif kind == "on_chat_model_end":
                    message = event["data"]["output"]
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        yield _chunk({
                            "role": "assistant",
                            "tool_calls": [
                                {"index": i, **_format_tool_call(tc)}
                                for i, tc in enumerate(message.tool_calls)
                            ],
                        })

            yield _chunk({}, finish_reason="stop")
            yield "data: [DONE]\n\n"

        except Exception:
            logger.exception("Error in stream")
            yield "data: " + json.dumps({"error": {"message": "Internal server error", "type": "server_error"}}) + "\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health(request: Request):
    initialized = request.app.state.agent_graph is not None
    body = {"status": "healthy" if initialized else "not_ready", "agent_initialized": initialized}
    if not initialized:
        return JSONResponse(status_code=503, content=body)
    return body


_BASE_DIR = Path(__file__).resolve().parent
_PLAYGROUND_HTML = _BASE_DIR / "playground" / "templates" / "index.html"
_IMAGES_DIR = _BASE_DIR / "images"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def playground():
    if _auth_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(_PLAYGROUND_HTML)


@app.get("/images/{filename:path}", include_in_schema=False)
async def serve_image(filename: str):
    if _auth_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    base = _IMAGES_DIR.resolve()
    file_path = (base / filename).resolve()
    try:
        file_path.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=404, detail="Image not found")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)


if __name__ == "__main__":
    import uvicorn

    port = int(getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
