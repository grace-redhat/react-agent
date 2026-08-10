import httpx

from os import getenv
from typing import Any
import logging

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from react_agent.tools import calculator, fetch_page

logger = logging.getLogger(__name__)

GITHUB_TOOLS_ALLOWLIST = {"get_issue", "create_issue"}

def get_graph_closure(
    model_id: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    mcp_tools: list[Any] | None = None,
) -> Any:
    """Build and return a LangGraph ReAct agent with the configured LLM and tools.

    Creates a ChatOpenAI client, wires mcp tools,
    and uses create_agent to produce a graph that runs the ReAct loop (reason,
    act with tools, observe, repeat until a final answer).

    Args:
        model_id: LLM model identifier (e.g. for OpenAI-compatible API). Uses MODEL_ID env if omitted.
        base_url: Base URL for the LLM API. Uses BASE_URL env if omitted.
        api_key: API key for the LLM. Uses API_KEY env if omitted; required for non-local base_url.

    Returns:
        A LangGraph agent (CompiledGraph) that accepts {"messages": [...]} and returns updated state.
    """

    if not api_key:
        api_key = getenv("API_KEY")
    if not base_url:
        base_url = getenv("BASE_URL")
    if not model_id:
        model_id = getenv("MODEL_ID")

    if not base_url:
        raise ValueError(
            "BASE_URL is required. Set it via argument or BASE_URL env var."
        )
    is_local = any(host in base_url for host in ["localhost", "127.0.0.1"])

    if not is_local and not api_key:
        raise ValueError("API_KEY is required for non-local environments.")

    tools = [calculator, fetch_page] + [t for t in (mcp_tools or []) if t.name in GITHUB_TOOLS_ALLOWLIST]

    logger.info(f"tools: {[tool.name for tool in tools]}")

    chat = ChatOpenAI(
        model=model_id,
        temperature=0.01,
        api_key=api_key,
        base_url=base_url,
        streaming=False,
        http_client=httpx.Client(verify=False),
        http_async_client=httpx.AsyncClient(verify=False),
    )

    system_prompt = """You are a helpful assistant. When you receive a result from a tool,
        use that information to provide a FINAL answer to the user immediately.
        Do NOT call tools repeatedly for the same question."""
    agent = create_agent(model=chat, tools=tools, system_prompt=system_prompt)
    

    return agent
