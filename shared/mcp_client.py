"""Helper to connect to a remote MCP worker and call tools."""

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


async def call_remote_tool(endpoint: str, tool_name: str, arguments: dict | None = None, timeout: float = 120) -> str:
    """Connect to a remote MCP server and call a tool. Returns the text result."""
    async with streamablehttp_client(endpoint, timeout=timeout) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            return "\n".join(parts) or "(no output)"


async def list_remote_tools(endpoint: str, timeout: float = 30) -> list[dict]:
    """Connect to a remote MCP server and list its tools."""
    async with streamablehttp_client(endpoint, timeout=timeout) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {"name": t.name, "description": t.description or ""}
                for t in result.tools
            ]
