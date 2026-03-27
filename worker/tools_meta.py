"""Meta-tools for dynamic tool creation/management at runtime."""

import json

from worker import tools_dynamic

_mcp = None


async def create_tool(name: str, description: str, python_code: str, params: str = None) -> str:
    """Create a new MCP tool at runtime. The tool becomes immediately available.

    name: tool function name (snake_case, e.g. 'check_docker_status')
    description: what the tool does (shown to Claude)
    python_code: the Python function body (has access to os, subprocess, json, Path, time, re, math, platform, urllib, shutil)
    params: optional JSON string of parameter definitions, e.g. '[{"name": "path", "type": "str"}, {"name": "count", "type": "int", "default": 10}]'
           supported types: str, int, float, bool, list, dict
    """
    parsed_params = None
    if params:
        try:
            parsed_params = json.loads(params)
        except json.JSONDecodeError as e:
            return f"Invalid params JSON: {e}"

    return tools_dynamic.create_and_register(_mcp, name, description, python_code, parsed_params)


async def list_dynamic_tools() -> str:
    """List all dynamically created tools with their descriptions."""
    tools = tools_dynamic.list_all()
    if not tools:
        return "No dynamic tools created yet."
    lines = []
    for t in tools:
        param_info = ""
        if t.get("params"):
            param_names = [p["name"] for p in t["params"]]
            param_info = f"({', '.join(param_names)})"
        lines.append(f"- {t['name']}{param_info}: {t['description']}")
    return "\n".join(lines)


async def remove_dynamic_tool(name: str) -> str:
    """Remove a dynamically created tool by name."""
    return tools_dynamic.remove(_mcp, name)


def register(mcp):
    global _mcp
    _mcp = mcp
    mcp.tool()(create_tool)
    mcp.tool()(list_dynamic_tools)
    mcp.tool()(remove_dynamic_tool)
