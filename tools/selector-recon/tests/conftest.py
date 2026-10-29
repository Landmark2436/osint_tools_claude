"""Shared test fixtures. Tests never touch the internet: modules talk to a local HTTP server."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from selector_recon.http import HttpClient
from selector_recon.modules import RunContext

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureServer:
    """Serves canned responses: routes[(method, path)] = (status, body, headers)."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], tuple[int, str, dict[str, str]]] = {}
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _serve(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                server.requests.append((self.command, self.path, dict(self.headers), body))
                method = "GET" if self.command == "HEAD" else self.command
                status, text, headers = server.routes.get((method, self.path), (404, "no route", {}))
                payload = text.encode("utf-8")
                self.send_response(status)
                for k, v in {"Content-Type": "text/html; charset=utf-8", **headers}.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(payload)

            do_GET = do_POST = do_HEAD = _serve

            def log_message(self, *args: object) -> None:
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def add(self, path: str, status: int = 200, body: str = "", method: str = "GET", headers: dict[str, str] | None = None) -> None:
        self.routes[(method, path)] = (status, body, headers or {})

    def add_fixture(self, path: str, fixture: str, status: int = 200, method: str = "GET") -> None:
        self.add(path, status, (FIXTURES / "http" / fixture).read_text(encoding="utf-8"), method)

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    s = FixtureServer()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def no_proxy(monkeypatch):
    """Keep local test traffic away from any proxy configured in the environment."""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def ctx(tmp_path):
    http = HttpClient(timeout=5, rate=0)
    c = RunContext(http=http, out_dir=tmp_path / "out", cache_dir=tmp_path / "cache", options={"workers": 4})
    yield c
    http.close()


def load_fixture_json(name: str, base: str) -> dict:
    """Load a JSON fixture and replace {BASE} with the local server URL."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8").replace("{BASE}", base))
