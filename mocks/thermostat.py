"""Mock thermostat service.

Run: uvicorn mocks.thermostat:app --host 0.0.0.0 --port 9002
OpenAPI: http://localhost:9002/openapi.json
"""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="Mock Thermostat",
    description="In-memory mock thermostat for testing AI-driven smart-home automation.",
    version="0.1.0",
)

Mode = Literal["heat", "cool", "auto", "off"]


class State(BaseModel):
    current_temp_c: float = 21.5
    target_temp_c: float = 22.0
    mode: Mode = "auto"
    humidity_pct: int = 45


_state = State()


@app.get("/state", operation_id="get_thermostat_state")
def get_state() -> State:
    """Get the current thermostat state (temperature, target, mode, humidity)."""
    return _state


class TargetUpdate(BaseModel):
    target_temp_c: float = Field(ge=10, le=32, description="Target temperature in Celsius")


@app.put("/target", operation_id="set_thermostat_target")
def set_target(update: TargetUpdate) -> State:
    """Set the target temperature in Celsius (10-32)."""
    _state.target_temp_c = update.target_temp_c
    return _state


class ModeUpdate(BaseModel):
    mode: Mode


@app.put("/mode", operation_id="set_thermostat_mode")
def set_mode(update: ModeUpdate) -> State:
    """Set the operating mode: heat, cool, auto, or off."""
    _state.mode = update.mode
    return _state
