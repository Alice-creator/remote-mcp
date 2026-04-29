"""Translates a tool call into an HTTP request against a device's API."""

import json

import httpx

from gateway.devices import Device
from gateway.openapi import ToolDef


def _apply_auth(headers: dict, auth: dict | None) -> None:
    if not auth:
        return
    auth_type = auth.get("type")
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {auth.get('token', '')}"
    elif auth_type == "api_key":
        headers[auth.get("header", "X-API-Key")] = auth.get("value", "")
    elif auth_type == "header":
        headers[auth.get("name", "X-Custom")] = auth.get("value", "")


def _format_error(status: int, body: str) -> str:
    """Surface device errors to the AI in a compact, useful form.

    JSON bodies often have a `detail` (FastAPI), `message` (many APIs), or `error`
    field — extract that. HTML bodies usually just spam tags at the model; truncate.
    """
    body = body or ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            for key in ("detail", "message", "error"):
                if key in data and isinstance(data[key], (str, dict, list)):
                    val = data[key] if isinstance(data[key], str) else json.dumps(data[key])
                    return f"[HTTP {status}] {val}"
            return f"[HTTP {status}] {body}"
    except (json.JSONDecodeError, TypeError):
        pass

    if body.lstrip().startswith("<"):
        return f"[HTTP {status}] (HTML response, {len(body)} bytes — likely a server error page)"
    return f"[HTTP {status}] {body[:500]}{'…' if len(body) > 500 else ''}"


async def call(tool: ToolDef, device: Device, args: dict) -> str:
    args = args or {}

    path = tool.path_template
    for key in tool.path_keys:
        if key in args:
            path = path.replace("{" + key + "}", str(args[key]))

    query = {k: args[k] for k in tool.query_keys if k in args and args[k] is not None}
    body = {k: args[k] for k in tool.body_keys if k in args and args[k] is not None}

    url = device.base_url.rstrip("/") + path
    headers: dict = {}
    _apply_auth(headers, device.auth)

    async with httpx.AsyncClient(timeout=30) as client:
        kwargs: dict = {"params": query or None, "headers": headers}
        if tool.method in ("POST", "PUT", "PATCH"):
            kwargs["json"] = body
        resp = await client.request(tool.method, url, **kwargs)

    if resp.status_code >= 400:
        return _format_error(resp.status_code, resp.text)
    return resp.text or f"[HTTP {resp.status_code}] (empty body)"
