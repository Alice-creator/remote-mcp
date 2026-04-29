# Plexus

A protocol-agnostic gateway that lets **any AI model** control **any API-first device** through a single tool surface.

Point Plexus at an OpenAPI spec, and every operation in that spec becomes an AI tool — exposed simultaneously over MCP, REST, and an OpenAI-compatible chat proxy.

You register devices by pointing at their OpenAPI specs. The gateway parses each spec, generates tool definitions, and exposes them through:

- **MCP** (for Claude.ai and other MCP clients)
- **REST** (`/tools`, `/call`)
- **OpenAI-compatible chat proxy** (`/api/chat`) that runs the agent loop for you, so you can drive it with Ollama Cloud, OpenAI, OpenRouter, or any model that speaks function calling

A built-in web UI (`/`) gives you device management, manual tool invocation, and a chat playground.

First use case: smart home.

## Architecture

```
Browser UI  ────►  Gateway  ──┬──►  /api/chat   ──►  Ollama / OpenAI / ...
                              │                       (agent loop runs here)
Claude.ai   ────►  /mcp/      ├──►  Device 1 API (described by OpenAPI spec)
                              ├──►  Device 2 API
Any agent   ────►  /tools     └──►  ...
                  /call
```

- `workspace/devices/*.yaml` — one file per device (name, base URL, OpenAPI spec)
- The gateway fetches each spec on startup, generates tool defs, and registers them everywhere

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env to set PLEXUS_API_KEY for the chat proxy
```

## Run (local)

Open three terminals:

```bash
# Terminal 1 — mock lights service
uvicorn mocks.lights:app --port 9001

# Terminal 2 — mock thermostat service
uvicorn mocks.thermostat:app --port 9002

# Terminal 3 — gateway
python run_gateway.py
```

Then open <http://localhost:8000/> in your browser:

- **Devices** — `mock_lights` and `mock_thermostat` are already seeded in `workspace/devices/`
- **Tools** — auto-generated from each device's OpenAPI spec; click any tool to invoke it manually
- **Chat** — set your LLM base URL / model / API key in the gear menu, then chat

## Run (Docker)

```bash
docker compose up -d --build
```

Brings up gateway (port 8000) + both mocks (9001, 9002).

## Adding a new device

Either drop a YAML in `workspace/devices/`:

```yaml
name: home_assistant
description: My Home Assistant instance
base_url: http://homeassistant.local:8123
spec_url: http://homeassistant.local:8123/api/openapi.json
auth:
  type: bearer
  token: YOUR_LONG_LIVED_TOKEN
```

…or use the **+ Add device** form in the UI. Either way, the gateway re-reads the registry and re-fetches specs.

Auth types supported:

```yaml
auth: { type: bearer, token: "..." }
auth: { type: api_key, header: "X-API-Key", value: "..." }
auth: { type: header, name: "X-Custom-Auth", value: "..." }
```

## API reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/devices` | List registered devices |
| POST | `/api/devices` | Add a device (body matches YAML fields) |
| DELETE | `/api/devices/{name}` | Remove a device |
| GET | `/api/tools` | List all generated tools + schemas |
| POST | `/api/call` | `{tool, args}` — invoke one tool |
| POST | `/api/reload` | Re-scan registry + refetch all specs |
| POST | `/api/chat` | OpenAI-style agent loop (see `gateway/chat_proxy.py`) |
| ANY | `/mcp/` | MCP streamable-HTTP endpoint for Claude.ai etc. |

## Connecting Claude.ai

Expose the gateway via ngrok:

```bash
ngrok http 8000
```

In Claude.ai → **Settings → Connectors → Add custom connector**, paste `https://<your-ngrok>.ngrok-free.app/mcp/`.

## Layout

```
gateway/
  server.py          main entry: FastMCP + Starlette + UI
  config.py          env vars (PLEXUS_*, GATEWAY_PORT)
  devices.py         YAML registry
  openapi.py         spec parsing → ToolDef
  tool_registry.py   live tool index, dynamic function gen for FastMCP
  proxy.py           ToolDef + args → HTTP request
  http_api.py        REST endpoints used by the UI
  chat.py            /api/chat + /api/chat/stream agent loop
  ui.py              static-file mount
  static/            HTML/CSS/JS UI

mocks/
  lights.py          FastAPI mock smart-bulbs
  thermostat.py      FastAPI mock thermostat

workspace/devices/   user device registry (one YAML per device)
workspace/specs/     local OpenAPI specs referenced by spec_path

legacy/              the original Claude-Code-on-each-device worker model
                     plus the old shared/ helpers. Not on the v1 path; kept
                     for reference and possible revival for hardware that
                     doesn't have an HTTP API.
```
