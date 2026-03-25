# Remote MCP Server

A Python MCP server that lets you control your PC remotely from Claude.ai (e.g. from your phone). Includes a `claude_code` tool that delegates coding tasks to a persistent Claude Code session on the host machine.

## Tools

| Tool | Description |
|------|-------------|
| `execute_shell` | Run any shell command (30s default timeout, 60s max) |
| `read_file` | Read a file by absolute path |
| `write_file` | Write content to a file |
| `list_directory` | List files in a directory |
| `get_system_info` | CPU, memory, disk usage |
| `claude_code` | Send a coding task to Claude Code (persistent session) |

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
MCP_SECRET=your-strong-random-token
MCP_PORT=1000
CLAUDE_WORKING_DIR=C:/Project
```

### 3. Run the server

```bash
python main.py
```

### 4. Expose publicly

Use ngrok to create a public URL:

```bash
ngrok http 1000
```

Or deploy with Docker:

```bash
docker compose up -d --build
```

### 5. Connect from Claude.ai

Go to **Settings > Connectors > Add custom connector** and enter your public URL (e.g. `https://xxxx.ngrok-free.app`).

## Architecture

```
Phone (Claude.ai)
  → ngrok / Cloudflare Tunnel
    → MCP Server (streamable-http)
      → claude_code tool → Claude Code CLI (persistent session)
      → execute_shell, read_file, write_file, etc.
```
