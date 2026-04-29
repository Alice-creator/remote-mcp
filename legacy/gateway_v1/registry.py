"""Worker registry — stores known workers with TTL-based status."""

import json
import time
from pathlib import Path

from legacy.shared.models import WorkerInfo

REGISTRY_FILE = Path("workspace/registry.json")
OFFLINE_TTL = 90

_workers: dict[str, WorkerInfo] = {}


def register_worker(data: dict) -> bool:
    worker_id = data.get("worker_id")
    if not worker_id:
        return False

    _workers[worker_id] = WorkerInfo(
        worker_id=worker_id,
        name=data.get("name", "unknown"),
        endpoint=data.get("endpoint", ""),
        capabilities=data.get("capabilities", {}),
        tools=data.get("tools", []),
        status="online",
        last_heartbeat=time.time(),
    )
    _persist()
    return True


def get_worker(worker_id: str) -> WorkerInfo | None:
    _refresh_statuses()
    if worker_id in _workers:
        return _workers[worker_id]
    for w in _workers.values():
        if w.name == worker_id:
            return w
    return None


def get_all_workers() -> list[WorkerInfo]:
    _refresh_statuses()
    return list(_workers.values())


def remove_worker(worker_id: str) -> bool:
    if worker_id in _workers:
        del _workers[worker_id]
        _persist()
        return True
    return False


def _refresh_statuses():
    now = time.time()
    for w in _workers.values():
        if now - w.last_heartbeat > OFFLINE_TTL:
            w.status = "offline"


def _persist():
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for w in _workers.values():
        data.append({
            "worker_id": w.worker_id,
            "name": w.name,
            "endpoint": w.endpoint,
            "capabilities": w.capabilities,
            "tools": w.tools,
            "status": w.status,
            "last_heartbeat": w.last_heartbeat,
        })
    REGISTRY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_from_disk():
    if not REGISTRY_FILE.exists():
        return
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        for entry in data:
            _workers[entry["worker_id"]] = WorkerInfo(**entry)
        _refresh_statuses()
        print(f"[gateway] Loaded {len(_workers)} worker(s) from registry.")
    except Exception as e:
        print(f"[gateway] Failed to load registry: {e}")
