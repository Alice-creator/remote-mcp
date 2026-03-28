"""Gateway MCP server — routes tasks from Claude.ai to worker devices."""

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from shared.config import GATEWAY_PORT, FACTORY_SECRET
from gateway import registry, tools

mcp = FastMCP(
    "ai-factory-gateway",
    port=GATEWAY_PORT,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True),
)

tools.register(mcp)
registry.load_from_disk()


async def _register_endpoint(request: Request):
    """Handle worker registration heartbeats."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    if FACTORY_SECRET and data.get("secret") != FACTORY_SECRET:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if registry.register_worker(data):
        return JSONResponse({"status": "ok", "worker_id": data.get("worker_id")})
    return JSONResponse({"error": "Invalid registration data"}, status_code=400)


def run():
    print(f"[gateway] Starting on port {GATEWAY_PORT}")
    print(f"[gateway] Workers should POST heartbeats to http://<gateway>:{GATEWAY_PORT}/api/register")

    mcp_app = mcp.streamable_http_app()

    app = Starlette(
        routes=[
            Route("/api/register", _register_endpoint, methods=["POST"]),
        ],
    )
    app.mount("/", mcp_app)

    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
