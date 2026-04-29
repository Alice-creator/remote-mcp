"""Mock smart-lights service.

Run: uvicorn mocks.lights:app --host 0.0.0.0 --port 9001
OpenAPI: http://localhost:9001/openapi.json
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Mock Smart Lights",
    description="In-memory mock for testing AI-driven smart-home automation.",
    version="0.1.0",
)


class Light(BaseModel):
    id: str
    name: str
    on: bool = False
    brightness: int = Field(default=100, ge=0, le=100)
    color: str = "white"


_lights: dict[str, Light] = {
    "living_room": Light(id="living_room", name="Living Room"),
    "bedroom": Light(id="bedroom", name="Bedroom"),
    "kitchen": Light(id="kitchen", name="Kitchen"),
}


def _get(light_id: str) -> Light:
    if light_id not in _lights:
        raise HTTPException(404, f"Light '{light_id}' not found")
    return _lights[light_id]


@app.get("/lights", operation_id="list_lights")
def list_lights() -> list[Light]:
    """List all lights with their current state."""
    return list(_lights.values())


@app.get("/lights/{light_id}", operation_id="get_light")
def get_light(light_id: str) -> Light:
    """Get the state of one light by id."""
    return _get(light_id)


@app.post("/lights/{light_id}/on", operation_id="turn_on_light")
def turn_on(light_id: str) -> Light:
    """Turn a light on."""
    light = _get(light_id)
    light.on = True
    return light


@app.post("/lights/{light_id}/off", operation_id="turn_off_light")
def turn_off(light_id: str) -> Light:
    """Turn a light off."""
    light = _get(light_id)
    light.on = False
    return light


class LightUpdate(BaseModel):
    brightness: int | None = Field(default=None, ge=0, le=100)
    color: str | None = None


@app.put("/lights/{light_id}", operation_id="update_light")
def update_light(light_id: str, update: LightUpdate) -> Light:
    """Update a light's brightness and/or color (e.g. red, blue, warm_white)."""
    light = _get(light_id)
    if update.brightness is not None:
        light.brightness = update.brightness
    if update.color is not None:
        light.color = update.color
    return light
