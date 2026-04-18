"""Start the TimeBox app and open it automatically in the default browser."""
import os
import socket
import subprocess
import sys
import time
import webbrowser
from contextlib import closing
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parent


def free_port(default: int = 8000) -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        if sock.connect_ex(("127.0.0.1", default)) != 0:
            return default
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(base_url + "/api/health", timeout=1)
            return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Server did not start in time")


def main() -> int:
    port = free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--reload"],
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    try:
        wait_for_server(base_url)
        webbrowser.open(base_url + "/login")
        print(f"\n[TimeBox] App is running at {base_url}")
        print("[TimeBox] The browser should open automatically.")
        print("[TimeBox] Press Ctrl+C in this terminal to stop the app.\n")
        return process.wait()
    except KeyboardInterrupt:
        print("\n[TimeBox] Stopping app...")
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == '__main__':
    raise SystemExit(main())
