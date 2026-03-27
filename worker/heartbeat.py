"""Heartbeat: periodically registers this worker with the gateway."""

import threading
import uuid

import httpx

from shared.config import GATEWAY_URL, FACTORY_SECRET, WORKER_NAME, MCP_PORT
from worker import capabilities

_worker_id = str(uuid.uuid4())
_stop_event = threading.Event()


def _heartbeat_loop(endpoint: str, tools: list[str], interval: int = 30):
    caps = capabilities.detect()

    while not _stop_event.is_set():
        payload = {
            "worker_id": _worker_id,
            "name": WORKER_NAME,
            "endpoint": endpoint,
            "capabilities": caps,
            "tools": tools,
            "secret": FACTORY_SECRET,
        }
        try:
            resp = httpx.post(f"{GATEWAY_URL}/api/register", json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"[worker] Heartbeat OK → {GATEWAY_URL}")
            else:
                print(f"[worker] Heartbeat failed: {resp.status_code}")
        except Exception as e:
            print(f"[worker] Heartbeat error: {e}")

        _stop_event.wait(interval)


def start(tools: list[str], endpoint: str | None = None):
    if not GATEWAY_URL:
        print("[worker] No GATEWAY_URL set — heartbeat disabled.")
        return

    worker_endpoint = endpoint or f"http://localhost:{MCP_PORT}"
    thread = threading.Thread(
        target=_heartbeat_loop,
        args=(worker_endpoint, tools),
        daemon=True,
    )
    thread.start()
    print(f"[worker] Heartbeat started → {GATEWAY_URL} (worker: {WORKER_NAME})")


def stop():
    _stop_event.set()


def get_worker_id() -> str:
    return _worker_id
