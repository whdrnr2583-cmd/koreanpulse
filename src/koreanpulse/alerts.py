"""Webhook alert delivery — Discord, Telegram, Slack.

Crypto-native traders live in Discord/Telegram. The most common feature
request from this audience is "ping me when X happens" — not "let me poll
your MCP every minute". This module is the post-out side of that loop.

Delivery is fire-and-forget by design: alert formatting + transport
failures must never crash the calling tool. Errors get logged and
swallowed; the next alert tries fresh.

URL formats accepted:

    Discord:   https://discord.com/api/webhooks/<id>/<token>
    Slack:     https://hooks.slack.com/services/T.../B.../...
    Telegram:  tg://<bot_token>/<chat_id>
               or: https://api.telegram.org/bot<token>/sendMessage?chat_id=<id>

Telegram has no native "incoming webhook" pattern — we accept either the
shortcut `tg://` form or the explicit sendMessage URL with chat_id query.
"""
from __future__ import annotations

import enum
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qs, urlparse

import httpx

from agentprod import retry_async

logger = logging.getLogger(__name__)


class Channel(str, enum.Enum):
    DISCORD = "discord"
    SLACK = "slack"
    TELEGRAM = "telegram"
    UNKNOWN = "unknown"


@dataclass
class AlertResult:
    ok: bool
    channel: Channel
    status_code: Optional[int]
    error: Optional[str] = None


# ── URL classification ─────────────────────────────────────────────────────


_DISCORD_RE = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/")
_SLACK_RE = re.compile(r"^https://hooks\.slack\.com/services/")
_TG_API_RE = re.compile(r"^https://api\.telegram\.org/bot[^/]+/sendMessage")


def detect_channel(url: str) -> Channel:
    """Best-effort URL → Channel mapping."""
    if not url:
        return Channel.UNKNOWN
    if url.startswith("tg://"):
        return Channel.TELEGRAM
    if _TG_API_RE.match(url):
        return Channel.TELEGRAM
    if _DISCORD_RE.match(url):
        return Channel.DISCORD
    if _SLACK_RE.match(url):
        return Channel.SLACK
    return Channel.UNKNOWN


# ── Per-channel senders ────────────────────────────────────────────────────


async def _send_discord(url: str, *, title: str, body: str) -> AlertResult:
    """Discord webhook — embed for nice formatting."""
    payload = {
        "username": "koreanpulse",
        "embeds": [
            {
                "title": title[:256],
                "description": body[:4096],
                "color": 0xF0B429,  # matches brand
            }
        ],
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        async def _call() -> httpx.Response:
            return await client.post(url, json=payload)
        resp = await retry_async(_call, max_attempts=3, base_seconds=0.5)
    return AlertResult(
        ok=resp.is_success, channel=Channel.DISCORD, status_code=resp.status_code,
        error=None if resp.is_success else resp.text[:200],
    )


async def _send_slack(url: str, *, title: str, body: str) -> AlertResult:
    """Slack incoming webhook — Block Kit."""
    payload = {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
            {"type": "section", "text": {"type": "mrkdwn", "text": body[:3000]}},
        ]
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        async def _call() -> httpx.Response:
            return await client.post(url, json=payload)
        resp = await retry_async(_call, max_attempts=3, base_seconds=0.5)
    return AlertResult(
        ok=resp.is_success, channel=Channel.SLACK, status_code=resp.status_code,
        error=None if resp.is_success else resp.text[:200],
    )


async def _send_telegram(url: str, *, title: str, body: str) -> AlertResult:
    """Telegram bot sendMessage. Accepts shortcut `tg://<token>/<chat>` or
    explicit `https://api.telegram.org/bot<token>/sendMessage?chat_id=...`.
    """
    if url.startswith("tg://"):
        # tg://<bot_token>/<chat_id>
        rest = url[len("tg://"):]
        try:
            bot_token, chat_id = rest.split("/", 1)
        except ValueError:
            return AlertResult(
                ok=False, channel=Channel.TELEGRAM, status_code=None,
                error="malformed tg:// URL — expected tg://<bot_token>/<chat_id>",
            )
        api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {"chat_id": chat_id}
    else:
        parsed = urlparse(url)
        api_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        qs = parse_qs(parsed.query)
        chat_id_list = qs.get("chat_id", [])
        if not chat_id_list:
            return AlertResult(
                ok=False, channel=Channel.TELEGRAM, status_code=None,
                error="telegram URL missing chat_id query param",
            )
        params = {"chat_id": chat_id_list[0]}

    text = f"*{title}*\n\n{body}"[:4000]
    payload = {**params, "text": text, "parse_mode": "Markdown"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def _call() -> httpx.Response:
            return await client.post(api_url, data=payload)
        resp = await retry_async(_call, max_attempts=3, base_seconds=0.5)
    return AlertResult(
        ok=resp.is_success, channel=Channel.TELEGRAM, status_code=resp.status_code,
        error=None if resp.is_success else resp.text[:200],
    )


# ── Public API ─────────────────────────────────────────────────────────────


async def send_alert(url: str, *, title: str, body: str) -> AlertResult:
    """Send an alert to any supported webhook URL.

    Never raises on transport / formatting issues — returns AlertResult with
    `ok=False` and an `error` string instead. This keeps tool execution
    paths from being held hostage by webhook outages.
    """
    if not url:
        return AlertResult(
            ok=False, channel=Channel.UNKNOWN, status_code=None,
            error="empty webhook URL",
        )
    channel = detect_channel(url)
    try:
        if channel == Channel.DISCORD:
            return await _send_discord(url, title=title, body=body)
        if channel == Channel.SLACK:
            return await _send_slack(url, title=title, body=body)
        if channel == Channel.TELEGRAM:
            return await _send_telegram(url, title=title, body=body)
        return AlertResult(
            ok=False, channel=channel, status_code=None,
            error=f"unsupported webhook URL: {url[:80]}",
        )
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("alert send failed (%s): %s", channel.value, exc)
        return AlertResult(
            ok=False, channel=channel, status_code=None,
            error=f"{type(exc).__name__}: {exc}",
        )
