"""Gateway MCP tools — what Claude.ai sees and calls to reach workers."""

import json

from gateway import registry, dispatcher


async def list_workers() -> str:
    """List all registered workers with their status, capabilities, and available tools."""
    workers = registry.get_all_workers()
    if not workers:
        return "No workers registered."

    lines = []
    for w in workers:
        caps = ", ".join(k for k, v in w.capabilities.items() if v is True)
        lines.append(
            f"- **{w.name}** [{w.status}] ({w.capabilities.get('os', '?')})\n"
            f"  Endpoint: {w.endpoint}\n"
            f"  Capabilities: {caps or 'none detected'}\n"
            f"  Tools: {len(w.tools)} available"
        )
    return "\n\n".join(lines)


async def send_task(worker_id: str, tool_name: str, arguments: str = None) -> str:
    """Call a specific tool on a specific worker.

    worker_id: worker name or ID
    tool_name: the MCP tool to call on the worker
    arguments: optional JSON string of tool arguments, e.g. '{"command": "ls -la"}'
    """
    args = None
    if arguments:
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError as e:
            return f"Invalid arguments JSON: {e}"

    return await dispatcher.send_task(worker_id, tool_name, args)


async def send_claude_task(worker_id: str, prompt: str) -> str:
    """Send a natural-language task to a worker's Claude Code session.

    worker_id: worker name or ID
    prompt: the task description for Claude Code
    """
    return await dispatcher.send_task(worker_id, "claude_code", {"prompt": prompt}, timeout=300)


async def broadcast_task(tool_name: str, arguments: str = None) -> str:
    """Run the same tool on ALL online workers and return aggregated results.

    tool_name: the MCP tool to call
    arguments: optional JSON string of tool arguments
    """
    args = None
    if arguments:
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError as e:
            return f"Invalid arguments JSON: {e}"

    results = await dispatcher.broadcast_task(tool_name, args)
    lines = []
    for name, result in results.items():
        lines.append(f"### {name}\n{result}")
    return "\n\n".join(lines)


async def get_worker_tools(worker_id: str) -> str:
    """List all tools available on a specific worker (fetched live).

    worker_id: worker name or ID
    """
    result = await dispatcher.get_worker_tools(worker_id)
    if isinstance(result, str):
        return result
    lines = [f"- **{t['name']}**: {t['description']}" for t in result]
    return "\n".join(lines) or "No tools found."


async def create_remote_tool(worker_id: str, name: str, description: str, python_code: str, params: str = None) -> str:
    """Create a dynamic tool on a remote worker.

    worker_id: worker name or ID
    name: tool name (snake_case)
    description: what the tool does
    python_code: the Python function body
    params: optional JSON string of parameter definitions
    """
    arguments = {
        "name": name,
        "description": description,
        "python_code": python_code,
    }
    if params:
        arguments["params"] = params

    return await dispatcher.send_task(worker_id, "create_tool", arguments)


def register(mcp):
    mcp.tool()(list_workers)
    mcp.tool()(send_task)
    mcp.tool()(send_claude_task)
    mcp.tool()(broadcast_task)
    mcp.tool()(get_worker_tools)
    mcp.tool()(create_remote_tool)
