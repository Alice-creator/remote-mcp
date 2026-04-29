import os

from dotenv import load_dotenv

load_dotenv()

# Worker
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
CLAUDE_WORKING_DIR = os.getenv("CLAUDE_WORKING_DIR", "~/")

# Gateway
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8000"))

# Legacy worker bridge (kept for the modules under legacy/)
FACTORY_SECRET = os.getenv("FACTORY_SECRET", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "")
WORKER_NAME = os.getenv("WORKER_NAME", "unnamed-worker")
