from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from legacy.shared.config import MCP_PORT
from legacy.worker import tools_cli, tools_claude, tools_dynamic, tools_meta, heartbeat

mcp = FastMCP(
    "ai-factory-worker",
    port=MCP_PORT,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

tools_cli.register(mcp)
tools_claude.register(mcp)
tools_meta.register(mcp)
tools_dynamic.load_persisted_tools(mcp)


def run():
    tool_names = list(mcp._tool_manager._tools.keys())
    heartbeat.start(tool_names)
    print(f"[worker] Starting on port {MCP_PORT}")
    mcp.run(transport="streamable-http", mount_path="/")
