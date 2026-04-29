"""Mounts the static UI at /."""

from pathlib import Path

from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

STATIC_DIR = Path(__file__).parent / "static"


def routes():
    return [Mount("/", app=StaticFiles(directory=STATIC_DIR, html=True), name="ui")]
