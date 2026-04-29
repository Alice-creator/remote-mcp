"""Gateway server — wires FastMCP, the HTTP API, the chat proxy, and the UI."""

import logging
from pathlib import Path

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

from gateway import http_api, chat, tool_registry
from gateway.config import GATEWAY_PORT
from gateway.ui import routes as ui_routes

logger = logging.getLogger("gateway")

mcp = FastMCP(
    "plexus-gateway",
    port=GATEWAY_PORT,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _reload():
    n_devices, n_tools = tool_registry.reload(mcp)
    logger.info(f"Loaded {n_tools} tool(s) from {n_devices} device(s).")
    return n_devices, n_tools


def run():
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    _reload()

    mcp_app = mcp.streamable_http_app()

    routes = [
        *http_api.routes(_reload),
        *chat.routes(),
        Mount("/mcp", app=mcp_app),
        *ui_routes(),
    ]

    app = Starlette(routes=routes)

    print(f"[gateway] Starting on port {GATEWAY_PORT}")
    print(f"[gateway] UI:           http://localhost:{GATEWAY_PORT}/")
    print(f"[gateway] MCP endpoint: http://localhost:{GATEWAY_PORT}/mcp/")
    print(f"[gateway] HTTP API:     http://localhost:{GATEWAY_PORT}/api/...")

    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
