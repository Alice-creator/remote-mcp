import time
from dataclasses import dataclass, field


@dataclass
class WorkerInfo:
    worker_id: str
    name: str
    endpoint: str
    capabilities: dict = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    status: str = "online"
    last_heartbeat: float = field(default_factory=time.time)
