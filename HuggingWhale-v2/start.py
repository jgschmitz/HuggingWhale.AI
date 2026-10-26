"""Start API, durable worker, and Streamlit together in the active virtualenv."""
import subprocess
import sys
import time
from pathlib import Path

from whale_core.config import Settings


def main():
    root = Path(__file__).resolve().parent
    Settings.load(root / "config.local.json")
    processes = []
    commands = [
        ["-m", "uvicorn", "whale_core.api:app", "--host", "127.0.0.1", "--port", "8000"],
        ["-m", "whale_core.cli", "worker"],
        ["-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", "--server.port", "8501"],
    ]
    try:
        for args in commands:
            processes.append(subprocess.Popen([sys.executable, *args], cwd=root))
        print("HuggingWhale UI: http://127.0.0.1:8501 | API docs: http://127.0.0.1:8000/docs", flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in processes:
            if p.poll() is None:
                p.terminate()
        for p in processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    main()
