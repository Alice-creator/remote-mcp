"""
Auto-restart wrapper for main.py
Watches for file changes and restarts the MCP server automatically.
Usage: python run.py
"""

import subprocess
import sys
import time
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_FILES = {"main.py", "requirements.txt", ".env"}
SERVER_SCRIPT = Path(__file__).parent / "main.py"


class RestartHandler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.restart()

    def restart(self):
        if self.process and self.process.poll() is None:
            print("🛑 Stopping MCP server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

        print("🚀 Starting MCP server...")
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT)],
            cwd=str(SERVER_SCRIPT.parent),
        )
        print(f"✅ MCP server running (PID: {self.process.pid})")

    def on_modified(self, event):
        filename = Path(event.src_path).name
        if filename in WATCH_FILES:
            print(f"\n🔄 Detected change in '{filename}', restarting...")
            time.sleep(0.5)  # debounce
            self.restart()


if __name__ == "__main__":
    print("👀 Auto-restart watcher started. Watching for changes in main.py, .env...")
    print("   Press Ctrl+C to stop.\n")

    handler = RestartHandler()
    observer = Observer()
    observer.schedule(handler, path=str(SERVER_SCRIPT.parent), recursive=False)
    observer.start()

    try:
        while True:
            # Also restart if the process crashed
            if handler.process.poll() is not None:
                print("⚠️  Server crashed! Restarting in 2 seconds...")
                time.sleep(2)
                handler.restart()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        observer.stop()
        if handler.process and handler.process.poll() is None:
            handler.process.terminate()

    observer.join()
    print("👋 Watcher stopped.")
