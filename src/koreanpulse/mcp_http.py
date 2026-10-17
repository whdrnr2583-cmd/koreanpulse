"""ASGI entry for hosted koreanpulse MCP — streamable HTTP transport.

Exposes the same `mcp` instance as `koreanpulse.server` but as a Starlette
ASGI app suitable for uvicorn behind a reverse proxy (Caddy / nginx).

    uvicorn koreanpulse.mcp_http:app --host 127.0.0.1 --port 8400

The remote MCP path is `/mcp` to match ChatGPT and Claude.ai remote-MCP
expectations. License enforcement uses the same per-tool `license_key`
argument flow as stdio mode — production hosted needs one of:

  (preferred, hits D1 source-of-truth that webhook-worker writes)
    KOREANPULSE_VALIDATE_URL = https://api.koreanpulse.dev/v1/validate
    KOREANPULSE_CACHE_SHARED_SECRET = <hex shared with webhook-worker>

  (legacy, requires Postgres replica of D1)
    DATABASE_URL = postgres://...

Set whichever pair matches the deployment in the systemd EnvironmentFile
so license keys issued by the webhook process resolve here.

Root path `/` returns a plain-text guide so users who paste the bare
host into a browser see what to do next instead of a 404.
"""
from __future__ import annotations

import logging
import os

# uvicorn configures its own access logger; we still need basicConfig so
# `logger.info(...)` calls inside koreanpulse.server (per-tool tool_call
# instrumentation) actually reach stderr / mcp.log instead of being
# swallowed by the default WARNING-level root logger.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
# httpx logs every request URL at INFO, and DART request URLs carry the API
# key as a query parameter. Raise these two loggers so the key never reaches
# mcp.log; the koreanpulse.server tool_call INFO lines are unaffected.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from starlette.applications import Starlette  # noqa: E402 — must follow basicConfig above
from starlette.responses import PlainTextResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402

from koreanpulse.server import mcp  # noqa: E402 — importing before basicConfig swallows tool_call logs

if os.environ.get("KOREANPULSE_REQUIRE_LICENSE", "0").strip() == "1":
    _has_webhook = bool(
        os.environ.get("KOREANPULSE_VALIDATE_URL", "").strip()
        and os.environ.get("KOREANPULSE_CACHE_SHARED_SECRET", "").strip()
    )
    _has_postgres = bool(os.environ.get("DATABASE_URL", "").strip())
    if not (_has_webhook or _has_postgres):
        raise RuntimeError(
            "KOREANPULSE_REQUIRE_LICENSE=1 but neither validate-webhook nor "
            "Postgres is wired. Set either:\n"
            "  KOREANPULSE_VALIDATE_URL + KOREANPULSE_CACHE_SHARED_SECRET (preferred), or\n"
            "  DATABASE_URL (legacy Postgres replica).\n"
            "Hosted MCP must reach the same source-of-truth that the webhook "
            "process writes when Polar issues a license."
        )

_mcp_app = mcp.http_app(transport="streamable-http", path="/mcp")

def _root_body(base_url: str) -> str:
    """Banner text pointing at the address this server was actually reached on.

    The first-party hosted endpoint is paused, so the banner must not send a
    self-hoster to it; it advertises ``base_url`` (derived from the request).
    """
    mcp_url = f"{base_url.rstrip('/')}/mcp"
    return (
        "koreanpulse — MCP endpoint\n"
        "==========================\n"
        "\n"
        "This URL is the MCP server itself, not a web page. Connect it from\n"
        "an MCP-aware client that can reach this address:\n"
        "\n"
        f"  MCP URL: {mcp_url}\n"
        "\n"
        "  OpenAI Responses API:\n"
        f"    tools=[{{type: \"mcp\", server_url: \"{mcp_url}\"}}]\n"
        "\n"
        "7 MCP tools — 5 free (no key), 2 license-gated:\n"
        "  Free: track_korean_filings, search_korean_industry_news,\n"
        "    resolve_stock_code, lookup_corp_code, koreanpulse_about\n"
        "  License-gated: monitor_activist_investors, monitor_foreign_holders\n"
        "\n"
        "Source (AGPL):     https://github.com/whdrnr2583-cmd/koreanpulse\n"
        "Free daily digest: https://koreanpulse.dev\n"
        "PyPI:              https://pypi.org/project/koreanpulse/\n"
    )


async def _root(request):
    return PlainTextResponse(
        _root_body(str(request.base_url)), media_type="text/plain; charset=utf-8"
    )


app = Starlette(
    routes=[Route("/", _root), Mount("/", app=_mcp_app)],
    lifespan=_mcp_app.router.lifespan_context,
)
