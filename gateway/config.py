"""Plexus runtime configuration.

All env vars Plexus reads are defined here. `.env` (loaded via python-dotenv)
overrides the defaults; the chat tab in the UI can override per-request at runtime.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Gateway ---
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))

# --- LLM (OpenAI-compatible /chat/completions endpoint) ---
PLEXUS_BASE_URL = os.getenv("PLEXUS_BASE_URL", "https://ollama.com/v1")
PLEXUS_API_KEY = os.getenv("PLEXUS_API_KEY", "")
PLEXUS_MODEL = os.getenv("PLEXUS_MODEL", "gpt-oss:20b")
PLEXUS_SYSTEM_PROMPT = os.getenv(
    "PLEXUS_SYSTEM_PROMPT",
    "You are an assistant with access to a set of tools that interact with external "
    "services and devices. Use the tools when the user asks for information or actions "
    "that match their descriptions. Read tool results carefully before replying. "
    "Be concise.",
)
