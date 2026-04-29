"""Dynamic tool creation engine.

Compiles Python code strings into functions and registers them as MCP tools
on the live server. Persists tools to disk so they survive restarts.
"""

import json
import textwrap
from pathlib import Path

SANDBOX_MODULES = {
    "os": __import__("os"),
    "subprocess": __import__("subprocess"),
    "json": __import__("json"),
    "Path": Path,
    "time": __import__("time"),
    "re": __import__("re"),
    "math": __import__("math"),
    "platform": __import__("platform"),
    "urllib": __import__("urllib"),
    "shutil": __import__("shutil"),
}

DYNAMIC_TOOLS_FILE = Path("workspace/dynamic_tools.json")


def _load_persisted() -> list[dict]:
    if DYNAMIC_TOOLS_FILE.exists():
        try:
            return json.loads(DYNAMIC_TOOLS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_persisted(tools: list[dict]):
    DYNAMIC_TOOLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DYNAMIC_TOOLS_FILE.write_text(json.dumps(tools, indent=2), encoding="utf-8")


def _compile_tool(name: str, description: str, python_code: str, params: list[dict] | None = None) -> callable:
    """Compile a Python code string into a callable async function."""
    if params:
        param_parts = []
        type_map = {"str": "str", "int": "int", "float": "float", "bool": "bool", "list": "list", "dict": "dict"}
        for p in params:
            annotation = type_map.get(p.get("type", "str"), "str")
            if "default" in p:
                param_parts.append(f"{p['name']}: {annotation} = {repr(p['default'])}")
            else:
                param_parts.append(f"{p['name']}: {annotation}")
        sig = ", ".join(param_parts)
    else:
        sig = ""

    func_code = f"async def {name}({sig}):\n"
    func_code += f'    """{description}"""\n'
    func_code += textwrap.indent(python_code, "    ")

    namespace = {**SANDBOX_MODULES}
    exec(func_code, namespace)
    return namespace[name]


def create_and_register(mcp, name: str, description: str, python_code: str, params: list[dict] | None = None) -> str:
    """Create a dynamic tool, register it, and persist it."""
    try:
        fn = _compile_tool(name, description, python_code, params)
    except SyntaxError as e:
        return f"Syntax error in tool code: {e}"
    except Exception as e:
        return f"Error compiling tool: {e}"

    mcp.tool()(fn)

    tools = _load_persisted()
    tools = [t for t in tools if t["name"] != name]
    tools.append({
        "name": name,
        "description": description,
        "python_code": python_code,
        "params": params,
    })
    _save_persisted(tools)

    return f"Tool '{name}' created and registered."


def remove(mcp, name: str) -> str:
    """Remove a dynamic tool from the server and persistence."""
    existing = mcp._tool_manager._tools
    if name not in existing:
        return f"Tool '{name}' not found."

    del existing[name]

    tools = _load_persisted()
    tools = [t for t in tools if t["name"] != name]
    _save_persisted(tools)

    return f"Tool '{name}' removed."


def list_all() -> list[dict]:
    return _load_persisted()


def load_persisted_tools(mcp):
    """Load and register all previously persisted dynamic tools on startup."""
    tools = _load_persisted()
    loaded = 0
    for t in tools:
        try:
            fn = _compile_tool(t["name"], t["description"], t["python_code"], t.get("params"))
            mcp.tool()(fn)
            loaded += 1
        except Exception as e:
            print(f"[worker] Failed to load dynamic tool '{t['name']}': {e}")
    if loaded:
        print(f"[worker] Loaded {loaded} dynamic tool(s) from disk.")
