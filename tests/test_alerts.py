from __future__ import annotations

import httpx
import pytest

from koreanpulse.alerts import (
    AlertResult,
    Channel,
    detect_channel,
    send_alert,
)


class TestDetectChannel:
    def test_discord(self):
        assert (
            detect_channel("https://discord.com/api/webhooks/123/abc")
            == Channel.DISCORD
        )

    def test_discord_canary(self):
        assert (
            detect_channel("https://canary.discord.com/api/webhooks/1/x")
            == Channel.DISCORD
        )

    def test_slack(self):
        assert (
            detect_channel("https://hooks.slack.com/services/T1/B2/abc")
            == Channel.SLACK
        )

    def test_telegram_shortcut(self):
        assert detect_channel("tg://12345:abc/987") == Channel.TELEGRAM

    def test_telegram_explicit(self):
        url = "https://api.telegram.org/bot12345:abc/sendMessage?chat_id=987"
        assert detect_channel(url) == Channel.TELEGRAM

    def test_unknown(self):
        assert detect_channel("https://example.com/hook") == Channel.UNKNOWN

    def test_empty(self):
        assert detect_channel("") == Channel.UNKNOWN


class TestSendAlert:
    @pytest.mark.asyncio
    async def test_empty_url(self):
        r = await send_alert("", title="t", body="b")
        assert not r.ok
        assert r.channel == Channel.UNKNOWN
        assert "empty" in (r.error or "").lower()

    @pytest.mark.asyncio
    async def test_unknown_url(self):
        r = await send_alert("https://example.com", title="t", body="b")
        assert not r.ok
        assert r.channel == Channel.UNKNOWN
        assert "unsupported" in (r.error or "")

    @pytest.mark.asyncio
    async def test_discord_success(self, monkeypatch):
        captured = {}

        async def fake_send(self, **kwargs):  # noqa: ANN001
            captured["json"] = kwargs.get("json")
            captured["url"] = self.url if hasattr(self, "url") else None
            return httpx.Response(204, request=httpx.Request("POST", "http://x"))

        # Monkey-patch httpx.AsyncClient.post within send_alert's transport.
        async def mock_post(self, url, *, json=None, data=None):  # noqa: ANN001
            captured["url"] = url
            captured["json"] = json
            captured["data"] = data
            return httpx.Response(
                204, request=httpx.Request("POST", url)
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        r = await send_alert(
            "https://discord.com/api/webhooks/1/abc",
            title="Samsung filing",
            body="New 5% holder disclosure",
        )
        assert r.ok
        assert r.channel == Channel.DISCORD
        assert r.status_code == 204
        # Verify Discord embed shape
        assert captured["json"]["embeds"][0]["title"] == "Samsung filing"

    @pytest.mark.asyncio
    async def test_telegram_shortcut_success(self, monkeypatch):
        captured = {}

        async def mock_post(self, url, *, json=None, data=None):  # noqa: ANN001
            captured["url"] = url
            captured["data"] = data
            return httpx.Response(
                200, request=httpx.Request("POST", url)
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        r = await send_alert(
            "tg://1234567:bot_token/-100123",
            title="T",
            body="B",
        )
        assert r.ok
        assert r.channel == Channel.TELEGRAM
        assert "api.telegram.org/bot1234567:bot_token/sendMessage" in captured["url"]
        assert captured["data"]["chat_id"] == "-100123"

    @pytest.mark.asyncio
    async def test_telegram_explicit_url(self, monkeypatch):
        captured = {}

        async def mock_post(self, url, *, json=None, data=None):  # noqa: ANN001
            captured["url"] = url
            captured["data"] = data
            return httpx.Response(
                200, request=httpx.Request("POST", url)
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        r = await send_alert(
            "https://api.telegram.org/bot12:abc/sendMessage?chat_id=987",
            title="T",
            body="B",
        )
        assert r.ok
        assert captured["data"]["chat_id"] == "987"

    @pytest.mark.asyncio
    async def test_telegram_malformed_shortcut(self):
        r = await send_alert("tg://just_one_part", title="T", body="B")
        assert not r.ok
        assert "malformed" in (r.error or "")

    @pytest.mark.asyncio
    async def test_telegram_explicit_missing_chat(self):
        r = await send_alert(
            "https://api.telegram.org/bot12:abc/sendMessage", title="T", body="B"
        )
        assert not r.ok
        assert "chat_id" in (r.error or "")

    @pytest.mark.asyncio
    async def test_slack_block_kit(self, monkeypatch):
        captured = {}

        async def mock_post(self, url, *, json=None, data=None):  # noqa: ANN001
            captured["json"] = json
            return httpx.Response(
                200, request=httpx.Request("POST", url)
            )

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        r = await send_alert(
            "https://hooks.slack.com/services/T1/B2/abc",
            title="Activist alert",
            body="*KCGI* filed 5%",
        )
        assert r.ok
        assert captured["json"]["blocks"][0]["text"]["text"] == "Activist alert"

    @pytest.mark.asyncio
    async def test_transport_error_returns_failure(self, monkeypatch):
        async def mock_post(self, url, *, json=None, data=None):  # noqa: ANN001
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
        # retry_async will retry then re-raise; send_alert catches httpx.HTTPError
        r = await send_alert(
            "https://discord.com/api/webhooks/1/abc",
            title="T", body="B",
        )
        assert not r.ok
        assert "ConnectError" in (r.error or "")
