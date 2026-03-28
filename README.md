# AI Factory — Remote MCP

Multi-device Claude orchestration over MCP. Claude.ai on your phone/laptop delegates tasks to Claude Code instances running on your other devices (PCs, servers) via ngrok tunnels.

## Architecture

```
Claude.ai (phone/laptop)
  └── Gateway MCP Server        ← Claude.ai connects here
        ├── list_workers
        ├── send_task
        ├── send_claude_task
        ├── broadcast_task
        ├── get_worker_tools
        └── create_remote_tool
              │
              ├── Worker (office-pc)    ← ngrok tunnel
              ├── Worker (home-pc)      ← ngrok tunnel
              └── Worker (server)       ← ngrok tunnel
                    ├── execute_shell
                    ├── read_file / write_file / list_directory
                    ├── get_system_info
                    ├── claude_code          ← persistent Claude Code session
                    ├── claude_code_reset
                    ├── create_tool          ← dynamic tool creation
                    ├── list_dynamic_tools
                    └── remove_dynamic_tool
```

- **Gateway** — dumb router. Holds worker registry, forwards tool calls. Claude.ai is the brain.
- **Worker** — brains + hands on each device. Claude Code on each worker autonomously decides how to execute tasks, and can create new MCP tools at runtime.

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Gateway machine
GATEWAY_PORT=8000
FACTORY_SECRET=your-strong-shared-secret

# Worker machines (each device)
MCP_PORT=8001
WORKER_NAME=office-pc
CLAUDE_WORKING_DIR=~/Projects
GATEWAY_URL=https://<your-gateway-ngrok-url>
FACTORY_SECRET=your-strong-shared-secret  # same as gateway
```

### 3. Run

**Gateway** (one machine, exposed via ngrok):
```bash
python run_gateway.py
ngrok http 8000
```
Add the ngrok URL to Claude.ai: **Settings → Connectors → Add custom connector**.

**Each worker** (every device you want to control):
```bash
python run_worker.py
ngrok http 8001
# Set the ngrok URL as WORKER_NAME's endpoint in its .env
```

### 4. Docker (optional, single-machine testing)

```bash
docker compose up -d --build
```

This runs both gateway (port 8000) and worker (port 8001) on the same machine.

## Worker Tools

| Tool | Description |
|------|-------------|
| `execute_shell` | Run any shell command (60s max) |
| `read_file` | Read a file by absolute path |
| `write_file` | Write content to a file |
| `list_directory` | List files in a directory |
| `get_system_info` | CPU, memory, disk usage |
| `claude_code` | Send a task to a persistent Claude Code session |
| `claude_code_reset` | Kill and restart the Claude Code session |
| `create_tool` | Create a new MCP tool at runtime from Python code |
| `list_dynamic_tools` | List all dynamically created tools |
| `remove_dynamic_tool` | Remove a dynamic tool |

## Gateway Tools (what Claude.ai sees)

| Tool | Description |
|------|-------------|
| `list_workers` | Show all registered workers + status + capabilities |
| `send_task` | Call a specific tool on a specific worker |
| `send_claude_task` | Send a natural-language task to a worker's Claude Code |
| `broadcast_task` | Run the same tool on all online workers |
| `get_worker_tools` | List tools available on a specific worker |
| `create_remote_tool` | Create a dynamic tool on a remote worker |

## Dynamic Tools

Workers can create new MCP tools at runtime. Claude Code on a worker explores the device, then calls `create_tool` to build app-specific tools using real interfaces (CLIs, APIs, libraries) rather than generic GUI automation.

```
You: "Play my Liked Songs on Spotify on home-pc"
→ Worker's Claude Code: finds Spotify CLI → creates spotify_control tool → plays music
→ Next time: tool already exists, instant response
```

Dynamic tools persist to `workspace/dynamic_tools.json` and reload automatically on restart.
