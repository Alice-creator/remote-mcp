import json
import subprocess
import threading
import time

from shared.config import CLAUDE_WORKING_DIR

_claude_process: subprocess.Popen | None = None
_claude_lock = threading.Lock()
_claude_cwd: str = CLAUDE_WORKING_DIR


def _start_claude_process(cwd: str) -> subprocess.Popen:
    """Start a new persistent Claude Code process with stream-json I/O."""
    return subprocess.Popen(
        [
            "claude",
            "--print",
            "--input-format=stream-json",
            "--output-format=stream-json",
            "--dangerously-skip-permissions",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        bufsize=1,
    )


def _send_and_receive(process: subprocess.Popen, prompt: str, timeout: int = 120) -> str:
    """Send a prompt via stream-json and collect the full response."""
    message = json.dumps({"type": "user", "message": {"role": "user", "content": prompt}})
    try:
        process.stdin.write(message + "\n")
        process.stdin.flush()
    except BrokenPipeError:
        return "Error: Claude process pipe is broken — session will restart on next call."

    output_parts = []
    deadline = time.time() + timeout

    while time.time() < deadline:
        line = process.stdout.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            event_type = event.get("type", "")

            if event_type == "assistant":
                content = event.get("message", {}).get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        output_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        output_parts.append(block)

            elif event_type == "result":
                result_text = event.get("result", "")
                if result_text and result_text not in output_parts:
                    output_parts.append(result_text)
                break

            elif event_type == "error":
                return f"Claude error: {event.get('error', event)}"

        except json.JSONDecodeError:
            output_parts.append(line)

    if time.time() >= deadline:
        return f"Timed out waiting for Claude response after {timeout}s"

    return "\n".join(output_parts).strip() or "(no output)"


async def claude_code(prompt: str, working_directory: str = None) -> str:
    """Send a message to a persistent Claude Code session running on this PC.
    No new VSCode windows — uses a long-running background process with stream-json pipes.
    working_directory only takes effect when starting a fresh session."""
    global _claude_process, _claude_cwd

    cwd = working_directory or CLAUDE_WORKING_DIR

    with _claude_lock:
        if _claude_process is None or _claude_process.poll() is not None:
            print(f"[worker] Starting new Claude Code session in {cwd}")
            _claude_cwd = cwd
            _claude_process = _start_claude_process(cwd)
            time.sleep(1)

        return _send_and_receive(_claude_process, prompt)


async def claude_code_reset(working_directory: str = None) -> str:
    """Kill the current Claude Code session and start a fresh one."""
    global _claude_process, _claude_cwd

    cwd = working_directory or CLAUDE_WORKING_DIR

    with _claude_lock:
        if _claude_process and _claude_process.poll() is None:
            _claude_process.terminate()
            try:
                _claude_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _claude_process.kill()

        print(f"[worker] Resetting Claude Code session in {cwd}")
        _claude_cwd = cwd
        _claude_process = _start_claude_process(cwd)
        time.sleep(1)

    return f"Claude Code session reset. Working directory: {cwd}"


def register(mcp):
    """Register Claude Code tools on the given FastMCP server."""
    mcp.tool()(claude_code)
    mcp.tool()(claude_code_reset)
