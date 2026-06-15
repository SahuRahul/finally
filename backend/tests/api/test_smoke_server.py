"""Smoke test that boots a real uvicorn server and hits the key endpoints.

Guards against regressions that only appear under a real ASGI server (not the
in-process TestClient): SSE streaming, OpenAPI schema generation, and the
chat route being mounted.
"""

import os
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen

import pytest


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    """Launch the app under uvicorn with the simulator and mock LLM."""
    port = _free_port()
    env = {
        **os.environ,
        "FINALLY_DB_PATH": str(tmp_path / "smoke.db"),
        "LLM_MOCK": "true",
        "MASSIVE_API_KEY": "",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_until_up(base, proc)
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _wait_until_up(base: str, proc: subprocess.Popen) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early:\n{proc.stdout.read().decode()}")
        try:
            with urlopen(f"{base}/api/health", timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError("server did not become healthy in time")


def test_health(server):
    with urlopen(f"{server}/api/health", timeout=5) as r:
        assert r.status == 200


def test_openapi_schema(server):
    with urlopen(f"{server}/openapi.json", timeout=5) as r:
        assert r.status == 200


def test_sse_stream_emits_event(server):
    """GET /api/stream/prices must stream, not 422 on a missing query param."""
    deadline = time.time() + 10
    while time.time() < deadline:
        with urlopen(f"{server}/api/stream/prices", timeout=5) as r:
            assert r.status == 200
            assert "text/event-stream" in r.headers.get("content-type", "")
            for raw in r:
                line = raw.decode()
                if line.startswith("data:"):
                    return
        time.sleep(0.3)
    raise AssertionError("no SSE data event received")


def test_chat_route_mounted(server):
    """POST /api/chat must exist (mounted), not 404."""
    body = b'{"message": "hello"}'
    req = Request(
        f"{server}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=15) as r:
            assert r.status == 200
    except Exception as exc:  # HTTPError carries the status code
        code = getattr(exc, "code", None)
        assert code != 404, "POST /api/chat is not mounted (404)"
        assert code is not None and code < 500, f"chat route errored: {code}"
