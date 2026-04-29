"""Device registry — loads YAML device entries from workspace/devices/.

Each device is a YAML file with:
  name: snake_case unique id
  description: human-readable
  base_url: where the device's API lives
  spec_url: URL to OpenAPI spec  (one of spec_url/spec_path required)
  spec_path: local path to OpenAPI spec
  auth: (optional) {type: bearer|header|api_key, ...}
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEVICES_DIR = Path("workspace/devices")


@dataclass
class Device:
    name: str
    description: str = ""
    base_url: str = ""
    spec_url: str | None = None
    spec_path: str | None = None
    auth: dict | None = None


_devices: dict[str, Device] = {}


def load_all() -> list[Device]:
    """Reload the registry from disk."""
    _devices.clear()
    DEVICES_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted([*DEVICES_DIR.glob("*.yaml"), *DEVICES_DIR.glob("*.yml")]):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            d = Device(**data)
            _devices[d.name] = d
        except Exception as e:
            print(f"[gateway] Failed to load {f.name}: {e}")
    return list(_devices.values())


def all_devices() -> list[Device]:
    return list(_devices.values())


def get(name: str) -> Device | None:
    return _devices.get(name)


def add(device: Device) -> None:
    """Add or update a device, persisting to YAML."""
    DEVICES_DIR.mkdir(parents=True, exist_ok=True)
    data = {"name": device.name}
    if device.description:
        data["description"] = device.description
    if device.base_url:
        data["base_url"] = device.base_url
    if device.spec_url:
        data["spec_url"] = device.spec_url
    if device.spec_path:
        data["spec_path"] = device.spec_path
    if device.auth:
        data["auth"] = device.auth

    path = DEVICES_DIR / f"{device.name}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    _devices[device.name] = device


def remove(name: str) -> bool:
    if name not in _devices:
        return False
    path = DEVICES_DIR / f"{name}.yaml"
    if path.exists():
        path.unlink()
    del _devices[name]
    return True
