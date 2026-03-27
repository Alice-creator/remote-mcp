"""Dispatcher — forwards tool calls to remote workers via MCP client."""

from gateway import registry
from shared import mcp_client


async def send_task(worker_id: str, tool_name: str, arguments: dict | None = None, timeout: float = 120) -> str:
    worker = registry.get_worker(worker_id)
    if not worker:
        return f"Worker '{worker_id}' not found."
    if worker.status == "offline":
        return f"Worker '{worker.name}' is offline."

    try:
        return await mcp_client.call_remote_tool(worker.endpoint, tool_name, arguments, timeout=timeout)
    except Exception as e:
        return f"Error calling {tool_name} on {worker.name}: {e}"


async def get_worker_tools(worker_id: str) -> list[dict] | str:
    worker = registry.get_worker(worker_id)
    if not worker:
        return f"Worker '{worker_id}' not found."
    if worker.status == "offline":
        return f"Worker '{worker.name}' is offline."

    try:
        return await mcp_client.list_remote_tools(worker.endpoint)
    except Exception as e:
        return f"Error listing tools on {worker.name}: {e}"


async def broadcast_task(tool_name: str, arguments: dict | None = None, timeout: float = 120) -> dict[str, str]:
    workers = registry.get_all_workers()
    online = [w for w in workers if w.status == "online"]

    if not online:
        return {"error": "No online workers."}

    results = {}
    for worker in online:
        try:
            result = await mcp_client.call_remote_tool(worker.endpoint, tool_name, arguments, timeout=timeout)
            results[worker.name] = result
        except Exception as e:
            results[worker.name] = f"Error: {e}"

    return results
