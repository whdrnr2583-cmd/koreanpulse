"""ASGI entry for hosted koreanpulse MCP — streamable HTTP transport.

Exposes the same `mcp` instance as `koreanpulse.server` but as a Starlette
ASGI app suitable for uvicorn behind a reverse proxy (Caddy / nginx).

    uvicorn koreanpulse.mcp_http:app --host 127.0.0.1 --port 8400

The remote MCP path is `/mcp` to match ChatGPT and Claude.ai remote-MCP
expectations. License enforcement uses the same per-tool `license_key`
argument flow as stdio mode — set KOREANPULSE_REQUIRE_LICENSE=1 +
DATABASE_URL in the systemd EnvironmentFile so license keys issued by
the webhook process resolve here.
"""
from __future__ import annotations

import os

from koreanpulse.server import mcp

if os.environ.get("KOREANPULSE_REQUIRE_LICENSE", "0").strip() == "1" and not os.environ.get(
    "DATABASE_URL", ""
).strip():
    raise RuntimeError(
        "KOREANPULSE_REQUIRE_LICENSE=1 but DATABASE_URL is empty. "
        "Hosted MCP must share the Postgres license store with the webhook process."
    )

app = mcp.http_app(transport="streamable-http", path="/mcp")
