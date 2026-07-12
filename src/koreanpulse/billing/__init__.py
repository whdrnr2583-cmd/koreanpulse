"""Billing — historical Lemon Squeezy webhook handlers.

🚫 **NOT IN USE since 2026-05-06.** The Lemon Squeezy store application
was declined; Polar is now our sole billing provider, and active webhook
handling lives in `webhook-worker/src/polar.ts` (Cloudflare Worker + D1).
This Python module is retained as a historical implementation reference
only — no production traffic reaches these handlers.

Two pieces:
  - `lemonsqueezy.py` — pure functions: signature verify, event dispatch.
  - `webhook_app.py` — FastAPI app exposing POST /webhook/lemonsqueezy.

The MCP server (`koreanpulse.server`) and the (historical) webhook app
were designed to run as **separate processes**:
  - MCP server speaks stdio to Claude Desktop (or HTTP for cloud-hosted MCP).
  - Webhook app spoke HTTPS to Lemon Squeezy.
  - Both shared state via the LicenseStore (in-memory in v0, Postgres later).
"""
from __future__ import annotations
