"""The hosted, public Universal Paper MCP endpoint:  up-mcp --hosted  (served at https://mcp.universalpaper.org/mcp).

The same read-only tools as the local server (mcp_server.py), over Streamable HTTP, with these
differences, all of which follow from "confidential by construction":

- Stateless. Every request stands alone: no sessions, no storage, nothing written to disk.
- No file paths. A bundle is passed as an object or JSON text; the server never reads its own files.
- No access logs. Client addresses, headers and tool arguments are never logged or kept.
- Request counts only. The server counts calls per tool name and outcome, in memory, and shows
  the totals at /stats. A restart resets them. That is the whole of its usage signal.

Other routes: GET / (what this is, as JSON), GET /healthz (liveness).
"""
from __future__ import annotations

import os
import sys
import threading
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from . import SPEC, __version__
from .mcp_server import build_server

MAX_BODY = 2 * 1024 * 1024  # 2 MiB: far above any real bundle, small enough to bound the work per request
DOCS = "https://universalpaper.org/developers/#mcp"


class Usage:
    """Per-tool call counts. Holds tool names and outcomes only, never arguments or who called."""

    def __init__(self) -> None:
        self.started = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.calls: Counter[str] = Counter()
        self.errors: Counter[str] = Counter()
        self._lock = threading.Lock()

    def record(self, tool: str, ok: bool, seconds: float) -> None:
        with self._lock:
            self.calls[tool] += 1
            if not ok:
                self.errors[tool] += 1
        # One line per call for the host's log view: tool name, outcome and duration, nothing else.
        print(f"up-mcp call tool={tool} ok={int(ok)} ms={round(seconds * 1000)}", file=sys.stderr, flush=True)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"since": self.started, "total_calls": sum(self.calls.values()), "calls": dict(sorted(self.calls.items())),
                    "errors": dict(sorted(self.errors.items())),
                    "note": "Counts of tool calls by name since the server last started. No arguments, addresses or identities are kept."}


def create_app(usage: Usage | None = None):
    """The ASGI app: the MCP endpoint at /mcp plus /, /healthz and /stats."""
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    usage = usage or Usage()
    server = build_server(hosted=True, on_call=usage.record)

    @server.custom_route("/", methods=["GET"], include_in_schema=False)
    async def index(_: Request):
        return JSONResponse({
            "name": "Universal Paper MCP server", "spec": SPEC, "version": __version__,
            "endpoint": "/mcp", "transport": "streamable-http", "auth": "none",
            "read_only": True, "stateless": True, "docs": DOCS,
            "source": "https://github.com/Uppercentile/universal-paper",
            "privacy": "No sessions, storage, access logs or telemetry. Only per-tool call counts, shown at /stats.",
        })

    @server.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request):
        return JSONResponse({"ok": True})

    @server.custom_route("/stats", methods=["GET"], include_in_schema=False)
    async def stats(_: Request):
        return JSONResponse(usage.snapshot())

    # A public endpoint with no credentials and no state: DNS rebinding protection guards nothing here,
    # and it would reject the custom domain, so it is off.
    from mcp.server.transport_security import TransportSecuritySettings
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    try:  # MCP Python SDK 2.x
        app = server.streamable_http_app(stateless_http=True, json_response=True, transport_security=security,
                                         max_request_body_size=MAX_BODY, host="0.0.0.0")  # noqa: S104
    except TypeError:  # 1.x keeps these on settings
        server.settings.stateless_http = True
        server.settings.json_response = True
        server.settings.transport_security = security
        app = server.streamable_http_app()
    # Browser-based MCP clients (inspectors, directory playgrounds) need CORS. Nothing here uses cookies.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                       allow_headers=["*"], expose_headers=["Mcp-Session-Id", "Mcp-Protocol-Version"])
    return app


def serve(host: str | None = None, port: int | None = None) -> None:
    import uvicorn

    host = host or os.environ.get("HOST", "0.0.0.0")  # noqa: S104 (a container's public port)
    port = port or int(os.environ.get("PORT", "8080"))
    import logging

    # The SDK logs session chatter and tool errors (which can echo input). Keep only real failures.
    app = create_app()
    logging.getLogger("mcp").setLevel(logging.ERROR)
    print(f"up-mcp hosted: {SPEC}, v{__version__}, listening on {host}:{port} at /mcp", file=sys.stderr, flush=True)
    # access_log=False: client addresses and request lines are never written anywhere.
    uvicorn.run(app, host=host, port=port, access_log=False, server_header=False,
                proxy_headers=False, log_level="warning", timeout_graceful_shutdown=5)


if __name__ == "__main__":
    serve()
