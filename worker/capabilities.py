"""Auto-detect what this worker device can do."""

import platform
import shutil
import socket


def detect() -> dict:
    return {
        "os": platform.system(),
        "os_version": platform.release(),
        "hostname": socket.gethostname(),
        "arch": platform.machine(),
        "has_claude_code": shutil.which("claude") is not None,
        "has_docker": shutil.which("docker") is not None,
        "has_git": shutil.which("git") is not None,
        "has_python": shutil.which("python") is not None or shutil.which("python3") is not None,
        "has_node": shutil.which("node") is not None,
    }
