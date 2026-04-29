"""REST endpoints used by the UI and direct integrations.

  GET    /api/devices            list registered devices
  POST   /api/devices            add (or update) a device — body matches Device fields
  DELETE /api/devices/{name}     remove a device
  GET    /api/tools              list every tool currently exposed
  POST   /api/call               body: {tool, args} → invoke one tool
  POST   /api/reload             rescan workspace/devices/ and refetch all specs
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from gateway import devices, proxy, tool_registry


def _device_payload(d: devices.Device) -> dict:
    return {
        "name": d.name,
        "description": d.description,
        "base_url": d.base_url,
        "spec_url": d.spec_url,
        "spec_path": d.spec_path,
        "auth": d.auth,
    }


def routes(reload_fn):
    async def list_devices(request: Request):
        return JSONResponse([_device_payload(d) for d in devices.all_devices()])

    async def add_device(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)
        try:
            d = devices.Device(**data)
        except TypeError as e:
            return JSONResponse({"error": f"Invalid device fields: {e}"}, status_code=400)
        if not d.name:
            return JSONResponse({"error": "name is required"}, status_code=400)
        if not d.base_url:
            return JSONResponse({"error": "base_url is required"}, status_code=400)
        if not d.spec_url and not d.spec_path:
            return JSONResponse({"error": "spec_url or spec_path is required"}, status_code=400)

        devices.add(d)
        reload_fn()
        return JSONResponse({"status": "ok", "name": d.name})

    async def remove_device(request: Request):
        name = request.path_params["name"]
        if devices.remove(name):
            reload_fn()
            return JSONResponse({"status": "ok"})
        return JSONResponse({"error": f"Device '{name}' not found"}, status_code=404)

    async def list_tools(request: Request):
        return JSONResponse([
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "device": tool.device,
                "method": tool.method,
                "path": tool.path_template,
            }
            for tool, _ in tool_registry.get_index().values()
        ])

    async def call_tool(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        name = data.get("tool")
        args = data.get("args") or {}
        idx = tool_registry.get_index()
        if name not in idx:
            return JSONResponse({"error": f"Tool '{name}' not found"}, status_code=404)

        tool, device = idx[name]
        try:
            result = await proxy.call(tool, device, args)
            return JSONResponse({"result": result})
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def reload_endpoint(request: Request):
        n_devices, n_tools = reload_fn()
        return JSONResponse({"status": "ok", "devices": n_devices, "tools": n_tools})

    return [
        Route("/api/devices", list_devices, methods=["GET"]),
        Route("/api/devices", add_device, methods=["POST"]),
        Route("/api/devices/{name}", remove_device, methods=["DELETE"]),
        Route("/api/tools", list_tools, methods=["GET"]),
        Route("/api/call", call_tool, methods=["POST"]),
        Route("/api/reload", reload_endpoint, methods=["POST"]),
    ]
