import sys
import os
import ast
import operator as op
import httpx

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class SearchInput(BaseModel):
    """Schema for the search tool input."""

    query: str = Field(description="The value to search for.")

@tool("calculator", parse_docstring=True)
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.

    Args:
        expression: A string representing a mathematical expression. Example: "2 + 2"

    Returns:
        The result of the evaluated expression as a string.
    """
    # Define supported operators
    operators = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.Pow: op.pow,
        ast.BitXor: op.xor,
    }

    def eval_expr(node):
        if isinstance(node, ast.Num):  # <number>
            return node.n
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
        else:
            raise TypeError(f"Unsupported type: {type(node)}")

    try:
        # Parse the expression into an AST and evaluate it
        node = ast.parse(expression, mode='eval').body
        result = eval_expr(node)
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"

@tool("fetch_page", parse_docstring=True)
def fetch_page(url: str) -> str:
    """Fetch a web page and return its full content as clean markdown in a single call.

    Args:
        url: The full URL of the web page to fetch.

    Returns:
        The page content as markdown, or an error message if the fetch failed.
    """
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return "Error: FIRECRAWL_API_KEY is not set."

    try:
        response = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"url": url, "formats": ["markdown"]},
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json()["data"]["markdown"]
        max_chars = 12000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated to fit model context window.]"
        return content
    except Exception as e:
        return f"Error fetching {url}: {e}"

MCP_SERVER_CONFIG = {
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "transport": "stdio",
        "env": {**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_TOKEN", "")},
   },
}   
