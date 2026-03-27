import os

from dotenv import load_dotenv

load_dotenv()

# Server
MCP_PORT = int(os.getenv("MCP_PORT", "1000"))
CLAUDE_WORKING_DIR = os.getenv("CLAUDE_WORKING_DIR", "C:/Project")

# AI Factory
FACTORY_SECRET = os.getenv("FACTORY_SECRET", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "")
WORKER_NAME = os.getenv("WORKER_NAME", "unnamed-worker")
