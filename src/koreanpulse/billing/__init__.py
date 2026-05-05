"""Billing — Lemon Squeezy webhook handlers + license issuance.

Two pieces:
  - `lemonsqueezy.py` — pure functions: signature verify, event dispatch.
  - `webhook_app.py` — FastAPI app exposing POST /webhook/lemonsqueezy.

The MCP server (`koreanpulse.server`) and the webhook app run as **separate
processes** intentionally:
  - MCP server speaks stdio to Claude Desktop (or HTTP for cloud-hosted MCP).
  - Webhook app speaks HTTPS to Lemon Squeezy.
  - Both share state via the LicenseStore (in-memory in v0, Postgres later).
"""
from __future__ import annotations
