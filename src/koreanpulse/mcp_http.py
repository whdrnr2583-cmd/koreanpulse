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

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from koreanpulse.server import mcp

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

_ROOT_BODY = (
    "koreanpulse — hosted MCP endpoint\n"
    "==================================\n"
    "\n"
    "This URL is the MCP server itself, not a web page. Connect it from\n"
    "an MCP-aware client:\n"
    "\n"
    "  Claude.ai → Settings → Connectors → Add custom connector\n"
    "    URL: https://mcp.koreanpulse.dev/mcp\n"
    "\n"
    "  ChatGPT → Settings → Connectors → Add custom connector\n"
    "    URL: https://mcp.koreanpulse.dev/mcp\n"
    "\n"
    "  OpenAI Responses API:\n"
    "    tools=[{type: \"mcp\", server_url: \"https://mcp.koreanpulse.dev/mcp\"}]\n"
    "\n"
    "5 free tools (no key): track_korean_filings, search_korean_industry_news,\n"
    "  monitor_activist_investors (gate), monitor_foreign_holders (gate),\n"
    "  resolve_stock_code, lookup_corp_code, koreanpulse_about\n"
    "\n"
    "2 paid tools (Solo $29/mo+): activist_investors + foreign_holders\n"
    "  classification (KCGI / Align / BlackRock / Norges / etc).\n"
    "\n"
    "Pricing + signup:  https://koreanpulse.dev/#pricing\n"
    "Free daily digest: https://koreanpulse.dev/today\n"
    "Source (AGPL):     https://github.com/whdrnr2583-cmd/koreanpulse\n"
    "PyPI:              https://pypi.org/project/koreanpulse/\n"
)


async def _root(_request):
    return PlainTextResponse(_ROOT_BODY, media_type="text/plain; charset=utf-8")


app = Starlette(
    routes=[Route("/", _root), Mount("/", app=_mcp_app)],
    lifespan=_mcp_app.router.lifespan_context,
)
