"""Builds the live tool index from the device registry and registers each
tool as a callable function on the FastMCP server.

Why exec(): FastMCP introspects function signatures + docstrings to build the
MCP tool schema. To get a real signature for each OpenAPI operation, we
generate a small async function with typed parameters and bind it to the
proxy + ToolDef in its closure.
"""

from gateway import devices, openapi, proxy

_TYPE_MAP = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}

_RESERVED = {
    "False", "None", "True", "and", "as", "assert", "async", "await", "break",
    "class", "continue", "def", "del", "elif", "else", "except", "finally",
    "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
    "not", "or", "pass", "raise", "return", "try", "while", "with", "yield",
}


_index: dict[str, tuple[openapi.ToolDef, devices.Device]] = {}


def get_index() -> dict[str, tuple[openapi.ToolDef, devices.Device]]:
    return _index


def _build_handler(tool: openapi.ToolDef, device: devices.Device):
    """Generate an async function with a real signature derived from input_schema."""
    props = tool.input_schema.get("properties", {}) or {}
    required = set(tool.input_schema.get("required", []) or [])

    sig_parts = []
    arg_names = []
    for name, schema in props.items():
        # Avoid Python keyword collisions by suffixing — proxy gets the original name.
        py_name = f"{name}_" if name in _RESERVED else name
        py_type = _TYPE_MAP.get((schema or {}).get("type", "string"), "str")
        if name in required:
            sig_parts.append(f"{py_name}: {py_type}")
        else:
            sig_parts.append(f"{py_name}: {py_type} = None")
        arg_names.append((py_name, name))

    sig = ", ".join(sig_parts)
    args_dict = ", ".join(f"{orig!r}: {py}" for py, orig in arg_names)

    # repr() escapes any quotes/newlines safely; the resulting string literal
    # becomes the function's docstring (Python uses the first string-literal
    # statement as the docstring).
    func_src = (
        f"async def {tool.name}({sig}) -> str:\n"
        f"    {tool.description!r}\n"
        f"    _args = {{{args_dict}}}\n"
        f"    _args = {{k: v for k, v in _args.items() if v is not None}}\n"
        f"    return await _proxy_call(_tool, _device, _args)\n"
    )

    namespace = {"_proxy_call": proxy.call, "_tool": tool, "_device": device}
    exec(func_src, namespace)
    return namespace[tool.name]


def reload(mcp) -> tuple[int, int]:
    """Reload all devices, regenerate tools, register on FastMCP. Returns (devices, tools)."""
    _index.clear()
    # FastMCP doesn't expose a remove API; reach into the manager.
    mcp._tool_manager._tools.clear()

    device_list = devices.load_all()
    for device in device_list:
        try:
            spec = openapi.load_spec(device.spec_url, device.spec_path)
            tools = openapi.parse_spec(spec, device.name)
        except Exception as e:
            print(f"[gateway] Failed to load spec for {device.name}: {e}")
            continue

        for tool in tools:
            if tool.name in _index:
                existing_device = _index[tool.name][1].name
                print(
                    f"[gateway] Tool name collision: '{tool.name}' from {device.name} "
                    f"would shadow the same name from {existing_device} — skipping."
                )
                continue
            try:
                fn = _build_handler(tool, device)
                mcp.tool(name=tool.name, description=tool.description)(fn)
                _index[tool.name] = (tool, device)
            except Exception as e:
                print(f"[gateway] Failed to register tool {tool.name}: {e}")

    return len(device_list), len(_index)
