# AI Factory — Multi-Device Claude Orchestration

## Vision
One device (phone/PC) gives tasks to Claude. That Claude orchestrates other Claude instances across multiple devices. Each device runs a worker agent with full local access (files, shell, screen). Workers can **dynamically create adaptive MCP tools** at runtime — no generic GUI tools needed. Claude discovers what's on the device, then builds targeted tools for each app using its real interface (API, CLI, COM, etc.).

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                                │
│                                                                 │
│  Claude.ai = just the UI                                        │
│  User gives a command ("deploy my app", "check all servers")    │
│  Claude.ai passes it to the MCP server                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS (ngrok tunnel)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GATEWAY MCP SERVER                            │
│                    (the task router)                             │
│                                                                 │
│  Receives user commands via Claude.ai                           │
│  Knows which devices are available and what they can do          │
│  Delegates tasks to the right device(s)                         │
│                                                                 │
│  ┌──────────┐  ┌────────────┐  ┌───────────────────────┐       │
│  │ Registry │  │ Dispatcher │  │ Tools                 │       │
│  │          │  │            │  │                       │       │
│  │ which    │  │ routes     │  │ list_workers          │       │
│  │ workers  │◄─┤ tasks to   │  │ send_task             │       │
│  │ are      │  │ the right  │  │ send_claude_task      │       │
│  │ online?  │  │ device     │  │ broadcast_task        │       │
│  │          │  │            │  │ get_worker_tools      │       │
│  └────▲─────┘  └─────┬─────┘  │ create_remote_tool    │       │
│       │              │        └───────────────────────┘       │
│       │ heartbeat    │ MCP client (streamable-http)            │
└───────┼──────────────┼────────────────────────────────────────┘
        │              │
  ┌─────┘              └──────────────┬──────────────┐
  │                                   │              │
  ▼                                   ▼              ▼
┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│   WORKER DEVICE    │ │   WORKER DEVICE    │ │   WORKER DEVICE    │
│   Windows PC       │ │   Linux laptop     │ │   Mac mini         │
│                    │ │                    │ │                    │
│  ┌──────────────┐  │ │  ┌──────────────┐  │ │  ┌──────────────┐  │
│  │ Claude Code  │  │ │  │ Claude Code  │  │ │  │ Claude Code  │  │
│  │ (THE BRAIN)  │  │ │  │ (THE BRAIN)  │  │ │  │ (THE BRAIN)  │  │
│  │              │  │ │  │              │  │ │  │              │  │
│  │ Receives job │  │ │  │ Receives job │  │ │  │ Receives job │  │
│  │ Decides HOW  │  │ │  │ Decides HOW  │  │ │  │ Decides HOW  │  │
│  │ to do it     │  │ │  │ to do it     │  │ │  │ to do it     │  │
│  │ Creates own  │  │ │  │ Creates own  │  │ │  │ Creates own  │  │
│  │ tools        │  │ │  │ tools        │  │ │  │ tools        │  │
│  │ Explores     │  │ │  │ Explores     │  │ │  │ Explores     │  │
│  │ device       │  │ │  │ device       │  │ │  │ device       │  │
│  └──────────────┘  │ │  └──────────────┘  │ │  └──────────────┘  │
│                    │ │                    │ │                    │
│  MCP Server +      │ │  MCP Server +      │ │  MCP Server +      │
│  Dynamic Tools +   │ │  Dynamic Tools +   │ │  Dynamic Tools +   │
│  ngrok tunnel      │ │  ngrok tunnel      │ │  ngrok tunnel      │
└────────────────────┘ └────────────────────┘ └────────────────────┘
         │                     │                     │
         ▼                     ▼                     ▼
   Local Hardware        Local Hardware        Local Hardware
```

**Key insight**: Intelligence lives on each device. Each worker's Claude Code receives a job and **autonomously decides** how to accomplish it — exploring the device, creating tools, running commands. The gateway is just a router. Claude.ai is just a UI.

### Worker Internal Architecture

Each worker is a self-contained MCP server with layered tool sets:

```
┌─────────────────────────────────────────────────────────┐
│                    Worker MCP Server                     │
│                (FastMCP, streamable-http)                │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              TOOL REGISTRY                       │    │
│  │                                                  │    │
│  │  ┌─────────────┐  ┌──────────────────────────┐  │    │
│  │  │  CLI Tools  │  │    Claude Code Tools     │  │    │
│  │  │             │  │                          │  │    │
│  │  │ exec_shell  │  │ claude_code              │  │    │
│  │  │ read_file   │  │   └─ persistent process  │  │    │
│  │  │ write_file  │  │      stream-json pipes   │  │    │
│  │  │ list_dir    │  │      thread-safe lock    │  │    │
│  │  │ sys_info    │  │ claude_code_reset        │  │    │
│  │  └─────────────┘  └──────────────────────────┘  │    │
│  │                                                  │    │
│  │  ┌─────────────┐  ┌──────────────────────────┐  │    │
│  │  │ Meta Tools  │  │    Dynamic Tools         │  │    │
│  │  │             │  │    (created at runtime)   │  │    │
│  │  │ create_tool─┼──►                          │  │    │
│  │  │ list_tools  │  │ spotify_play     (user)  │  │    │
│  │  │ remove_tool─┼──► docker_status    (user)  │  │    │
│  │  │             │  │ read_excel       (user)  │  │    │
│  │  └─────────────┘  │ ...any tool Claude needs │  │    │
│  │                    └──────────────────────────┘  │    │
│  └──────────────────────────────────────────────────┘    │
│                                                         │
│  ┌──────────────┐  ┌─────────────────────────────────┐  │
│  │  Heartbeat   │  │  Capabilities Detection         │  │
│  │              │  │                                  │  │
│  │ POST every   │  │  os, arch, hostname              │  │
│  │ 30s to       │  │  has_claude_code, has_docker     │  │
│  │ Commander    │  │  has_git, has_python, has_node   │  │
│  └──────────────┘  └─────────────────────────────────┘  │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │  Dynamic Tool Persistence                           ││
│  │  workspace/dynamic_tools.json                       ││
│  │  Auto-reload on server restart                      ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Gateway Internal Architecture

The gateway is not an AI — it's just plumbing. It holds the worker registry, dispatches tool calls to the right worker, and exposes everything as MCP tools for Claude.ai to use.

```
┌───────────────────────────────────────────────────────────────┐
│                  Gateway MCP Server                           │
│            (FastMCP + Starlette custom routes)                │
│                                                               │
│  ┌──────────────────────┐    ┌─────────────────────────────┐  │
│  │   HTTP Endpoints     │    │   MCP Tools                 │  │
│  │                      │    │   (Claude.ai calls these)   │  │
│  │  POST /api/register  │    │                             │  │
│  │    ↓                 │    │  list_workers               │  │
│  │  ┌────────────────┐  │    │  send_task ──────────────┐  │  │
│  │  │   Registry     │  │    │  send_claude_task ───────┤  │  │
│  │  │                │  │    │  broadcast_task ─────────┤  │  │
│  │  │  WorkerInfo[]  │  │    │  get_worker_tools ───────┤  │  │
│  │  │  - id          │  │    │  create_remote_tool ─────┤  │  │
│  │  │  - name        │◄─┼────┤                         │  │  │
│  │  │  - endpoint    │  │    └─────────────────────────┼──┘  │
│  │  │  - capabilities│  │                              │     │
│  │  │  - tools[]     │  │    ┌─────────────────────────▼──┐  │
│  │  │  - status      │  │    │     Dispatcher             │  │
│  │  │  - last_beat   │  │    │     (dumb pipe)            │  │
│  │  └────────────────┘  │    │                            │  │
│  │  TTL: 90s → offline  │    │  lookup worker endpoint    │  │
│  │  Persisted to disk   │    │  open MCP client session   │  │
│  └──────────────────────┘    │  call_tool / list_tools    │  │
│                              │  return result             │  │
│  No intelligence here.       └────────────────────────────┘  │
│  Claude.ai decides what                                      │
│  to call and when.                                           │
└───────────────────────────────────────────────────────────────┘
```

### Data Flow: Task Execution

User gives a high-level command. Gateway delegates. Worker's Claude Code figures out the rest.

```
 User (Phone)                   Gateway                     Worker
     │                            │                           │
     │  "run tests on             │                           │
     │   office-pc"               │                           │
     │                            │                           │
     ├─── send_claude_task() ────►│                           │
     │    ("office-pc",           │                           │
     │     "run the tests")       │                           │
     │                            ├── lookup registry         │
     │                            │   endpoint: https://...   │
     │                            │                           │
     │                            ├── forward to worker ─────►│
     │                            │   claude_code("run the    │
     │                            │   tests")                 │
     │                            │                           │
     │                            │                    ┌──────┤
     │                            │                    │Claude│
     │                            │                    │Code  │
     │                            │                    │THINKS│
     │                            │                    │      │
     │                            │                    │"I'll │
     │                            │                    │find  │
     │                            │                    │the   │
     │                            │                    │test  │
     │                            │                    │files,│
     │                            │                    │run   │
     │                            │                    │pytest│
     │                            │                    │fix if│
     │                            │                    │fail" │
     │                            │                    └──────┤
     │                            │                           │
     │                            │◄──── result ──────────────┤
     │◄─── result ────────────────┤  "5 passed, 0 failed"    │
     │                            │                           │
```

### Data Flow: Adaptive Tool Creation (Worker-Driven)

Worker's Claude Code explores the device and creates its own tools as needed.

```
 User (Phone)                   Gateway                     Worker
     │                            │                           │
     │  "check GPU temp           │                           │
     │   on office-pc"            │                           │
     │                            │                           │
     ├── send_claude_task() ─────►│                           │
     │   ("office-pc",            │                           │
     │    "check GPU temp")       ├── forward ──────────────►│
     │                            │                           │
     │                            │                    ┌──────┤
     │                            │                    │Claude│
     │                            │                    │Code  │
     │                            │                    │THINKS│
     │                            │                    │      │
     │                            │                    │"no   │
     │                            │                    │GPU   │
     │                            │                    │tool  │
     │                            │                    │yet,  │
     │                            │                    │let me│
     │                            │                    │check │
     │                            │                    │what's│
     │                            │                    │avail"│
     │                            │                    │      │
     │                            │                    │> exec│
     │                            │                    │  nvidia-smi
     │                            │                    │      │
     │                            │                    │"ok,  │
     │                            │                    │I'll  │
     │                            │                    │create│
     │                            │                    │a tool│
     │                            │                    │for   │
     │                            │                    │next  │
     │                            │                    │time" │
     │                            │                    │      │
     │                            │                    │> create_tool(
     │                            │                    │  "check_gpu")
     │                            │                    │      │
     │                            │                    │> check_gpu()
     │                            │                    │  → 72°C
     │                            │                    └──────┤
     │                            │                           │
     │                            │◄── "GPU is at 72°C" ──────┤
     │◄── "GPU is at 72°C" ──────┤                           │
     │                            │                           │
     │  Next time same request    │                           │
     │  → tool already exists     │                           │
     │  → instant response        │                           │
```

### Data Flow: Worker Registration & Heartbeat

```
 Worker                                          Gateway
   │                                                │
   │  ── startup ──                                 │
   │  detect capabilities                           │
   │  (OS, docker, git, claude, etc.)               │
   │                                                │
   ├── POST /api/register ─────────────────────────►│
   │   {                                            │
   │     worker_id: "uuid",                    ┌────┤
   │     name: "office-pc",                    │validate
   │     endpoint: "https://xxx.ngrok.app",    │secret
   │     capabilities: {os, has_docker, ...},  │store in
   │     tools: ["execute_shell", ...],        │registry
   │     secret: "shared-secret"               └────┤
   │   }                                            │
   │◄── 200 OK ────────────────────────────────────┤
   │                                                │
   │  ... every 30 seconds ...                      │
   ├── POST /api/register (heartbeat) ─────────────►│
   │◄── 200 OK ────────────────────────────────────┤
   │                                                │
   │  ... 90s no heartbeat → gateway marks offline  │
```

### Network Topology

```
┌─────────────────────────────────────────────────────────┐
│                      INTERNET                            │
│                                                         │
│   ┌──────────────┐                                      │
│   │  Claude.ai   │ (Anthropic cloud)                    │
│   │  = THE BRAIN │                                      │
│   │  User on     │                                      │
│   │  phone/laptop│                                      │
│   └──────┬───────┘                                      │
│          │ HTTPS (Custom Connector)                      │
│          ▼                                              │
│   ┌──────────┐      ┌──────────┐      ┌──────────┐     │
│   │  ngrok   │      │  ngrok   │      │  ngrok   │     │
│   │ tunnel A │      │ tunnel B │      │ tunnel C │     │
│   └────┬─────┘      └────┬─────┘      └────┬─────┘     │
│        │                 │                 │            │
└────────┼─────────────────┼─────────────────┼────────────┘
         │                 │                 │
    ┌────▼─────┐     ┌────▼─────┐     ┌────▼─────┐
    │ Gateway  │     │ Worker B │     │ Worker C │
    │+ Worker A│     │ :1000    │     │ :1000    │
    │ :1000    │     │ Linux    │     │ Mac      │
    │ Windows  │     └──────────┘     └──────────┘
    └──────────┘
    (gateway + worker can be on the same device)
```

### Protocol Stack

```
Claude.ai → Gateway:
┌────────────────────────────────────────┐
│  Claude.ai (UI, passes user commands)  │  Interface
├────────────────────────────────────────┤
│  MCP (Model Context Protocol)          │  Tool calls
│  - tool/call, tool/list                │
├────────────────────────────────────────┤
│  Streamable HTTP Transport             │  MCP transport
│  - POST with SSE streaming responses   │
├────────────────────────────────────────┤
│  HTTPS (TLS via ngrok)                 │  Encryption
├────────────────────────────────────────┤
│  TCP/IP                                │  Network
└────────────────────────────────────────┘

Gateway → Worker (same protocol, gateway is MCP client):
┌────────────────────────────────────────┐
│  Dispatcher (task router)              │  Routing
├────────────────────────────────────────┤
│  MCP Client Session                    │  Tool calls
│  - session.call_tool()                 │
│  - session.list_tools()                │
├────────────────────────────────────────┤
│  Streamable HTTP Client                │  MCP transport
├────────────────────────────────────────┤
│  HTTPS (ngrok tunnel)                  │  Encryption
└────────────────────────────────────────┘

Worker → Gateway (heartbeat, plain REST):
┌────────────────────────────────────────┐
│  Heartbeat thread (every 30s)          │
├────────────────────────────────────────┤
│  HTTP POST /api/register               │  REST
│  JSON body + shared secret             │
├────────────────────────────────────────┤
│  HTTPS                                 │  Encryption
└────────────────────────────────────────┘
```

### Component Dependency Graph

```
main.py
  └── config.py (FACTORY_ROLE)
        │
        ├── FACTORY_ROLE=worker ──► worker/server.py
        │                              ├── tools_cli.py      (no deps)
        │                              ├── tools_claude.py   (← config.py)
        │                              ├── tools_meta.py     (← tools_dynamic.py)
        │                              ├── tools_dynamic.py  (standalone engine)
        │                              └── heartbeat.py      (← config.py, capabilities.py)
        │                                    └── capabilities.py (no deps)
        │
        └── FACTORY_ROLE=commander ──► commander/server.py (gateway)
                                          ├── registry.py        (← shared/models.py)
                                          ├── dispatcher.py      (← registry, shared/mcp_client.py)
                                          └── tools_orchestrate.py (← registry, dispatcher)

Intelligence lives on each DEVICE (Claude Code).
Claude.ai = UI. Gateway = router. Workers = brains + hands.
```

## Philosophy: Adaptive Tools over Generic GUI

Instead of generic GUI tools (click x,y / type text / OCR), Claude creates **app-specific tools** on demand:

| Need | Generic GUI approach | Adaptive tool approach |
|------|---------------------|----------------------|
| Control Spotify | Screenshot → find play button → click coords | `create_tool("spotify_play")` using Spotify CLI/API |
| Read Excel data | Screenshot → OCR → parse text | `create_tool("read_excel")` using openpyxl |
| Check Docker status | Screenshot terminal → OCR | `create_tool("docker_status")` using `docker ps` |
| Control Chrome | Screenshot → find element → click | `create_tool("chrome_open")` using Chrome DevTools Protocol |

The worker provides `execute_shell` + `get_system_info` as the "eyes" for Claude to discover what's on the device, then Claude creates proper tools to interact.

## File Structure

```
remote-mcp/
  main.py                        # Thin launcher (worker or commander mode)
  run.py                         # Dev auto-restart (unchanged)
  requirements.txt               # Updated deps
  .env.example                   # New config vars

  ai_factory/
    __init__.py
    config.py                    # Centralized env config

    worker/
      __init__.py
      server.py                  # Worker MCP server (CLI + Claude + dynamic tools)
      tools_cli.py               # execute_shell, read_file, write_file, list_directory, get_system_info
      tools_claude.py            # claude_code, claude_code_reset (persistent session)
      tools_dynamic.py           # Dynamic tool creation engine (exec + persist)
      tools_meta.py              # create_tool, list_dynamic_tools, remove_tool
      heartbeat.py               # POST registration to commander every 30s
      capabilities.py            # Auto-detect: OS, has_claude_code, installed apps, etc.

    commander/
      __init__.py
      server.py                  # Commander MCP server
      registry.py                # Worker registry (in-memory + file-persisted)
      dispatcher.py              # Connect to workers via MCP client, call tools
      tools_orchestrate.py       # list_workers, send_task, send_claude_task, broadcast_task

    shared/
      __init__.py
      models.py                  # Pydantic: WorkerInfo, TaskRequest, TaskResult
      auth.py                    # Shared-secret validation
      mcp_client.py              # streamable-http MCP client helper
```

## Key Design Decisions

1. **No generic GUI tools** — dynamic tool creation replaces them. Claude builds app-specific tools using real interfaces (APIs, CLIs, libraries)
2. **Dynamic tools are the core feature** — `exec()` based, persisted, hot-reloaded. Security already moot since `execute_shell` exists
3. **Single endpoint per worker** — CLI + Claude Code + dynamic tools all on one MCP server
4. **Gateway is a dumb MCP server** — Claude.ai is the brain, gateway is just plumbing
5. **Workers push to gateway** (heartbeat) — works with NAT/ngrok, no scanning needed

## Gateway MCP Tools (what Claude.ai sees)

| Tool | Description |
|------|-------------|
| `list_workers` | Show all registered workers + capabilities + status |
| `send_task(worker_id, tool_name, args)` | Call a tool on a specific worker |
| `send_claude_task(worker_id, prompt)` | Send a coding task to a worker's Claude Code |
| `broadcast_task(tool_name, args)` | Run same tool on ALL online workers |
| `get_worker_tools(worker_id)` | List tools available on a worker |
| `create_remote_tool(worker_id, name, desc, code)` | Create a dynamic tool on a remote worker |

## Worker Meta-Tools (Dynamic Creation)

| Tool | Description |
|------|-------------|
| `create_tool(name, description, params, python_code)` | Create & register a new tool at runtime |
| `list_dynamic_tools` | List all dynamically created tools |
| `remove_dynamic_tool(name)` | Remove a dynamic tool |

## New .env Config

```env
# Existing
MCP_SECRET=your-strong-random-token
MCP_PORT=1000
CLAUDE_WORKING_DIR=C:/Project

# New — AI Factory
FACTORY_ROLE=worker              # "worker" or "gateway"
FACTORY_SECRET=shared-secret     # Auth between nodes
GATEWAY_URL=                     # Workers set this to register with gateway
WORKER_NAME=office-pc            # Human-readable worker name
```

## Implementation Phases

### Phase 1: Restructure into package
- Extract current `main.py` tools into `ai_factory/worker/` modules
- Create `ai_factory/config.py` for centralized env loading
- `main.py` becomes thin launcher
- **Zero behavior change** — all 7 existing tools work identically
- **Test**: `python main.py` → connect from Claude.ai → all tools work

### Phase 2: Dynamic tool creation (core feature)
- `tools_dynamic.py` — compile Python code strings into functions via `exec()`, register on live server, persist to `workspace/dynamic_tools.json`
- `tools_meta.py` — `create_tool`, `list_dynamic_tools`, `remove_dynamic_tool`
- Support parameters (typed arguments from JSON schema)
- Auto-reload persisted tools on server restart
- **Test**: Create a tool via MCP call, then invoke it in the same session

### Phase 3: Gateway + worker registration
- `shared/mcp_client.py` — connect to remote workers via streamable-http MCP client
- `commander/registry.py` — store workers with TTL-based online/offline status
- `worker/heartbeat.py` — workers POST to gateway every 30s with their ngrok URL + capabilities
- `commander/dispatcher.py` — forward tool calls to correct worker
- `commander/tools_orchestrate.py` — gateway MCP tools that Claude.ai uses to reach workers
- **Test**: Claude.ai calls `send_task("office-pc", "execute_shell", {"command":"hostname"})` via gateway

### Phase 4: Polish & hardening
- Retry/timeout logic for dispatcher
- Task history and logging
- Better error messages when workers go offline
- Optional: simple web dashboard showing worker status

## How Dynamic Tool Creation Works

1. Claude explores the device via `execute_shell` (e.g. `pip list`, `docker --version`, `where chrome`)
2. Claude decides it needs a tool for a specific app
3. Calls `create_tool(name="spotify_play", description="Play/pause Spotify", python_code="...")` using the app's real interface
4. Engine compiles code string into a function via `exec()` with access to standard libs
5. Registers function on the live FastMCP server via `mcp.add_tool()`
6. Tool is immediately available — Claude can call it right away
7. Persisted to `workspace/dynamic_tools.json` for restart survival
8. On server restart, all dynamic tools are reloaded automatically

## How Worker Registration Works

```
Worker boots
  → detects capabilities (OS, installed CLIs, has_claude_code)
  → POST to Gateway's /api/register with:
    { worker_id, name, endpoint (ngrok URL), capabilities, tools[], secret }
  → Gateway stores in registry
  → Worker heartbeats every 30s
  → If no heartbeat for 90s → Gateway marks worker "offline"
```

## How Task Dispatch Works

```
User on phone: "Check docker status on office-pc"
  → Claude.ai DECIDES to call send_task (this is the key — AI decides, not the gateway)
  → send_task(worker_id="office-pc", tool_name="execute_shell", args={"command": "docker ps"})
  → Gateway looks up office-pc → endpoint: "https://abc.ngrok-free.app"
  → Gateway opens MCP client connection, forwards the call
  → Returns result to Claude.ai → Claude.ai interprets and responds to user
```

## Example Usage Scenarios

### Scenario 1: Code from phone
```
You (phone) → "Write a REST API for user auth in the backend project on office-pc"
Gateway → delegates to office-pc's Claude Code
Worker (office-pc) Claude Code:
  → explores project structure
  → writes the code
  → creates a "run_tests" tool
  → runs tests, fixes failures
  → returns: "Done. API created at src/auth.py, all 12 tests passing."
```

### Scenario 2: Adaptive app control
```
You (phone) → "Play my Liked Songs on Spotify on home-pc"
Gateway → delegates to home-pc's Claude Code
Worker (home-pc) Claude Code:
  → exec("where spotify") → finds Spotify
  → exec("spotify --help") → discovers CLI flags
  → creates "spotify_control" tool for future use
  → runs spotify URI to play liked songs
  → returns: "Playing Liked Songs on Spotify."
```

### Scenario 3: Multi-device broadcast
```
You → "What's the disk usage on all my machines?"
Gateway → broadcast_task("get_system_info") to all workers
Each worker returns its own system info
Gateway aggregates → returns combined report
```

### Scenario 4: Complex task — worker figures it out
```
You → "Backup the database on prod-server and restore it on dev-server"
Gateway → sends job to prod-server Claude Code
prod-server Claude Code:
  → explores what DB is running (postgres? mysql?)
  → creates "pg_dump_tool" dynamically
  → dumps the database
  → returns dump file path
Gateway → sends next job to dev-server Claude Code with dump info
dev-server Claude Code:
  → creates "pg_restore_tool" dynamically
  → restores the dump
  → returns: "Database restored. 42 tables, 1.2GB."
```
