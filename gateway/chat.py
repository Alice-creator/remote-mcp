"""Agent loop that calls an OpenAI-compatible LLM with the registered tools.

Two endpoints share one implementation (`_agent_loop`):

  POST /api/chat
    body: { messages, model?, base_url?, api_key?, system?, max_iterations? }
    response: { messages: [...full history...], trace: [{tool, args, result}, ...] }

  POST /api/chat/stream      (Server-Sent Events)
    body: same
    response: text/event-stream — emits one event per agent step:
      data: {"type": "tool_call",   "id", "name", "args"}
      data: {"type": "tool_result", "id", "name", "result"}
      data: {"type": "message",     "content"}
      data: {"type": "done"}                                    # terminal
      data: {"type": "error",       "error"}                    # terminal
      data: {"type": "final",       "messages": [...]}          # always last

Works against any OpenAI-compatible /chat/completions endpoint.
"""

import json
from typing import AsyncIterator

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from gateway import config, proxy, tool_registry


def _tools_payload() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            },
        }
        for tool, _ in tool_registry.get_index().values()
    ]


async def _llm_call(messages, tools, api_key, base_url, model):
    body: dict = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=body,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM error {resp.status_code}: {resp.text}")
        return resp.json()


def _prepare(data: dict):
    """Validate input and return (messages, api_key, base_url, model, max_iterations).
    Returns a JSONResponse on validation failure."""
    messages = list(data.get("messages") or [])
    if not messages:
        return JSONResponse({"error": "messages is required"}, status_code=400)

    api_key = data.get("api_key") or config.PLEXUS_API_KEY
    base_url = data.get("base_url") or config.PLEXUS_BASE_URL
    model = data.get("model") or config.PLEXUS_MODEL
    system = data.get("system") or config.PLEXUS_SYSTEM_PROMPT
    max_iterations = int(data.get("max_iterations") or 8)

    if system and not any(m.get("role") == "system" for m in messages):
        messages = [{"role": "system", "content": system}, *messages]

    return messages, api_key, base_url, model, max_iterations


async def _agent_loop(
    messages: list,
    api_key: str,
    base_url: str,
    model: str,
    max_iterations: int,
) -> AsyncIterator[dict]:
    """Run the agent loop, yielding one structured event per step.
    Mutates `messages` in place so callers can inspect the full history afterward."""
    tools = _tools_payload()
    idx = tool_registry.get_index()

    for _ in range(max_iterations):
        try:
            completion = await _llm_call(messages, tools, api_key, base_url, model)
        except Exception as e:
            yield {"type": "error", "error": f"LLM call failed: {e}"}
            return

        choice = completion["choices"][0]
        assistant_msg = choice["message"]
        messages.append(assistant_msg)

        tool_calls = assistant_msg.get("tool_calls") or []

        if not tool_calls:
            yield {"type": "message", "content": assistant_msg.get("content", "")}
            yield {"type": "done"}
            return

        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments") or "{}"
            try:
                fn_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                fn_args = {}

            yield {"type": "tool_call", "id": tc.get("id"), "name": fn_name, "args": fn_args}

            if fn_name in idx:
                tool, device = idx[fn_name]
                try:
                    result = await proxy.call(tool, device, fn_args)
                except Exception as e:
                    result = f"Error calling {fn_name}: {e}"
            else:
                result = f"Error: tool '{fn_name}' not registered"

            yield {"type": "tool_result", "id": tc.get("id"), "name": fn_name, "result": result}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "content": result,
            })

    yield {"type": "error", "error": f"Max iterations ({max_iterations}) reached"}


def routes():
    async def chat(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        prepared = _prepare(data)
        if isinstance(prepared, JSONResponse):
            return prepared
        messages, api_key, base_url, model, max_iterations = prepared

        trace: list[dict] = []
        async for event in _agent_loop(messages, api_key, base_url, model, max_iterations):
            t = event["type"]
            if t == "tool_call":
                # Append now; result is filled in by the matching tool_result event.
                trace.append({"tool": event["name"], "args": event["args"], "result": None})
            elif t == "tool_result":
                if trace and trace[-1]["result"] is None and trace[-1]["tool"] == event["name"]:
                    trace[-1]["result"] = event["result"]
            elif t == "error":
                return JSONResponse(
                    {"error": event["error"], "messages": messages, "trace": trace},
                    status_code=500,
                )

        return JSONResponse({"messages": messages, "trace": trace})

    async def chat_stream(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON"}, status_code=400)

        prepared = _prepare(data)
        if isinstance(prepared, JSONResponse):
            return prepared
        messages, api_key, base_url, model, max_iterations = prepared

        async def emit():
            async for event in _agent_loop(messages, api_key, base_url, model, max_iterations):
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'final', 'messages': messages})}\n\n"

        return StreamingResponse(
            emit(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return [
        Route("/api/chat", chat, methods=["POST"]),
        Route("/api/chat/stream", chat_stream, methods=["POST"]),
    ]
