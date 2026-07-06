import ast
import operator as op

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

@tool("search", parse_docstring=True)
def dummy_web_search(query: str) -> str:
    """Search the web for information about a specific topic.

    Placeholder implementation used by the ReAct agent; returns a fixed list
    for demonstration. Replace with a real search API in production.

    Args:
        query: The specific text string to search for. Example: "RedHat"

    Returns:
        A list of result strings (currently a single placeholder).
    """
    return "FINAL ANSWER: RedHat OpenShift AI. No further search needed."

MCP_SERVER_CONFIG = {                                                                                              
    "fetch": {                                                                                                     
        "command": "uvx",                                                                                          
        "args": ["mcp-server-fetch"],                                                                              
        "transport": "stdio",                                                                                      
   }                                                                                                              
}    