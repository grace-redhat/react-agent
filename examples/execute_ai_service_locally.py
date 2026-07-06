import asyncio
from os import getenv

from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from react_agent.tools import MCP_SERVER_CONFIG
from react_agent.agent import get_graph_closure

QUESTIONS = (
    "Fetch https://raw.githubusercontent.com/vllm-project/vllm/main/README.md and give me a 3-sentence summary of vLLM.",
    "How many GPU-hours to fine-tune a 7B model at 40 TFLOPS on 10B tokens? Assume 6 FLOPs per token per parameter.",
    "Fetch https://raw.githubusercontent.com/spiffe/spiffe/main/README.md and explain in 2 sentences what problem SPIFFE solves.",
    "What is 2 ** 32 and what would that be in gigabytes?",
)
DEBUG_MODE = True

class SimpleContext:
    """Simple context object for local execution that holds request payload and headers."""

    
    def __init__(self, payload=None):
        """Store the initial request payload (or an empty dict)."""
        self.request_payload_json = payload or {}

    def get_json(self):
        """Return the current request payload as a dict (e.g. messages for the agent)."""
        return self.request_payload_json

    def get_headers(self):
        """Return request headers; empty dict for local execution."""
        return {}



async def main():
    global DEBUG_MODE
    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")

    # Ensure base_url ends with /v1 if provided
    if base_url and not base_url.endswith("/v1"):
        base_url = base_url.rstrip("/") + "/v1"

    mcp_client = MultiServerMCPClient(MCP_SERVER_CONFIG)
    mcp_tools = await mcp_client.get_tools()

    agent = get_graph_closure(base_url=base_url, model_id=model_id,
  mcp_tools=mcp_tools)

    loop = asyncio.get_running_loop()

    print("\nSample questions:")
    for i, q in enumerate(QUESTIONS, 1):
        print(f"  {i}. {q}")
    print("\nType a number, ask your own question, press 'd' to toggle debug mode, or 'q' to quit.")

    while True:
        user_input = await loop.run_in_executor(None, input, "\n --> ")
        user_input = user_input.strip()

        if user_input.lower() in ("q", "quit"):
            break

        if user_input.lower() == "d":
            DEBUG_MODE = not DEBUG_MODE
            print(f"Debug mode {'on' if DEBUG_MODE else 'off'}.\n")
            continue

        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(QUESTIONS):
                user_input = QUESTIONS[idx]
                print(f"You chose: {user_input}\n")

        print()

        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=user_input)]},
            version="v2",
        ):
            kind = event["event"]
            if kind == "on_tool_start" and DEBUG_MODE:
                print(f"[Tool: {event['name']} → {event['data'].get('input', '')}]")
            elif kind == "on_tool_end" and DEBUG_MODE:
                output = str(event["data"].get("output", ""))
                print(f"[Result: {output[:300]}{'...' if len(output) > 300 else ''}]\n")
            elif kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    print(chunk.content, end="", flush=True)
            elif kind == "on_chat_model_end":
                msg = event["data"].get("output")
                if msg and hasattr(msg, "content"):
                    print(msg.content, end="", flush= True)
        print()


asyncio.run(main())