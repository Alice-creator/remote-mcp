import asyncio
import os
import platform
import subprocess
from pathlib import Path

import psutil
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

load_dotenv()

PORT = int(os.getenv("MCP_PORT"))
CLAUDE_WORKING_DIR = os.getenv("CLAUDE_WORKING_DIR", "C:/Project")
WSL_HOME = os.getenv("WSL_HOME", "/home/user")

mcp = FastMCP(
    "remote-pc-control",
    port=PORT,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def execute_shell(command: str, timeout: int = 30) -> str:
    """Run a shell command and return stdout/stderr. Timeout defaults to 30s."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=min(timeout, 60),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def read_file(path: str) -> str:
    """Read a file by absolute path and return its contents."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Write content to a file at the given absolute path."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@mcp.tool()
async def list_directory(path: str = ".") -> str:
    """List files and directories at the given path."""
    try:
        entries = []
        for entry in sorted(Path(path).iterdir()):
            kind = "dir" if entry.is_dir() else "file"
            size = entry.stat().st_size if entry.is_file() else 0
            entries.append(f"[{kind}] {entry.name}  ({size} B)" if size else f"[{kind}] {entry.name}")
        return "\n".join(entries) or "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


@mcp.tool()
async def get_system_info() -> str:
    """Return CPU, memory, and disk usage info."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (
            f"OS: {platform.system()} {platform.release()}\n"
            f"CPU: {psutil.cpu_count()} cores, {cpu_percent}% used\n"
            f"Memory: {mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB ({mem.percent}%)\n"
            f"Disk: {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)"
        )
    except Exception as e:
        return f"Error: {e}"


# Track whether a Claude Code session has been started
_claude_session_started = False


@mcp.tool()
async def claude_code(prompt: str, working_directory: str = None) -> str:
    """Send a message to Claude Code running on this PC.
    working_directory defaults to CLAUDE_WORKING_DIR from .env.
    For WSL paths, use the format: \\\\wsl$\\Ubuntu\\home\\username\\project
    The first call starts a new session, subsequent calls continue the same conversation."""
    global _claude_session_started
    cwd = working_directory or CLAUDE_WORKING_DIR
    try:
        cmd = ["claude", "-p", prompt]
        if _claude_session_started:
            cmd.append("--continue")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=cwd,
        )
        _claude_session_started = True
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Claude Code timed out after 5 minutes"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http", mount_path="/")
