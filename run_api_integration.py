"""
Harness to run live backend server and execute existing integration test suite.
"""
import os
import subprocess
import sys
import time
import requests

def main():
    backend_dir = os.path.abspath("backend")
    env = os.environ.copy()
    env["USE_MOCK_MONGO"] = "true"
    env["REACT_APP_BACKEND_URL"] = "http://127.0.0.1:8000"
    env["PYTHONPATH"] = backend_dir
    env["PYTHONUNBUFFERED"] = "1"
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["LANGSMITH_TRACING"] = "false"
    env["LANGCHAIN_TRACING_V2"] = "false"

    print("Starting uvicorn backend server on 127.0.0.1:8000...", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "info"],
        cwd=backend_dir,
        env=env,
    )

    started = False
    for i in range(60):
        time.sleep(1)
        if proc.poll() is not None:
            print(f"Server process terminated unexpectedly with code {proc.returncode}", flush=True)
            sys.exit(1)
        try:
            r = requests.get("http://127.0.0.1:8000/api/health", timeout=2)
            if r.status_code == 200 and r.json().get("status") == "ok":
                print(f"Backend healthy and fully seeded after {i+1}s: {r.json()}", flush=True)
                started = True
                break
        except Exception:
            if (i + 1) % 5 == 0:
                print(f"Waiting for backend startup ({i+1}s)...", flush=True)

    if not started:
        print("ERROR: Server failed to start within timeout.", flush=True)
        proc.terminate()
        sys.exit(1)

    print("\nRunning pytest backend/tests/test_backend_api.py against live server...\n", flush=True)
    test_res = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "backend/tests/test_backend_api.py",
            "-p",
            "no:langsmith",
            "-p",
            "no:anyio",
            "-v",
            "--tb=short",
        ],
        env=env,
    )

    print(f"\nIntegration tests exited with code {test_res.returncode}. Shutting down server...", flush=True)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

    sys.exit(test_res.returncode)

if __name__ == "__main__":
    main()

