from __future__ import annotations

import json

import httpx
import pytest

from koreanpulse.cache import FileCache
from koreanpulse.translate import (
    TranslationError,
    Translator,
)


class TestProviderDefaults:
    def test_openai_is_default(self, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_TRANSLATE_PROVIDER", raising=False)
        # Force re-import-time defaulting via direct constructor
        t = Translator(api_key="x")
        assert t.provider == "openai"
        assert t.model == "gpt-5-mini"

    def test_explicit_anthropic(self):
        t = Translator(provider="anthropic", api_key="x")
        assert t.provider == "anthropic"
        assert t.model.startswith("claude-haiku")

    def test_unknown_provider_raises(self):
        with pytest.raises(TranslationError, match="unknown provider"):
            Translator(provider="grok", api_key="x")

    def test_pricing_attached_per_provider(self):
        oai = Translator(provider="openai", api_key="x")
        ant = Translator(provider="anthropic", api_key="x")
        # OpenAI gpt-5-mini: 0.25/M input
        assert oai._pricing.input_per_1k == 0.00025
        # Anthropic Haiku 4.5: 1.0/M input
        assert ant._pricing.input_per_1k == 0.001

    def test_model_override(self):
        t = Translator(provider="openai", model="gpt-5", api_key="x")
        assert t.model == "gpt-5"


class TestApiKeyResolution:
    @pytest.mark.asyncio
    async def test_missing_openai_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        t = Translator(provider="openai")
        with pytest.raises(TranslationError, match="OPENAI_API_KEY"):
            await t.translate_ko_to_en("삼성전자")

    @pytest.mark.asyncio
    async def test_missing_anthropic_key_raises(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        t = Translator(provider="anthropic")
        with pytest.raises(TranslationError, match="ANTHROPIC_API_KEY"):
            await t.translate_ko_to_en("삼성전자")


class TestCacheBehavior:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        t = Translator(provider="openai", api_key="x")
        assert await t.translate_ko_to_en("") == ""
        assert await t.translate_ko_to_en("   ") == ""

    @pytest.mark.asyncio
    async def test_cache_returns_without_calling_llm(self, tmp_path):
        cache = FileCache(root=tmp_path / "cache")
        t = Translator(cache=cache, provider="openai", api_key="x")
        # Pre-seed cache for the exact key the translator will compute
        from koreanpulse.cache import cache_key
        key = cache_key("translate", "openai", "gpt-5-mini", "삼성전자")
        await cache.set(key, "Samsung Electronics")
        # Should hit cache, never call LLM
        out = await t.translate_ko_to_en("삼성전자")
        assert out == "Samsung Electronics"

    @pytest.mark.asyncio
    async def test_cache_key_includes_provider(self, tmp_path):
        # Same text, different provider → different cache key → different value possible
        from koreanpulse.cache import cache_key
        oai_key = cache_key("translate", "openai", "gpt-5-mini", "삼성전자")
        ant_key = cache_key("translate", "anthropic", "claude-haiku-4-5-20251001", "삼성전자")
        assert oai_key != ant_key


class TestCorpNameTranslation:
    """`translate_corp_name` is the dedicated single-name path used to fill
    `Filing.corp_name_en`. Separate cache namespace from filing titles."""

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        t = Translator(provider="openai", api_key="x")
        assert await t.translate_corp_name("") == ""
        assert await t.translate_corp_name("   ") == ""

    @pytest.mark.asyncio
    async def test_cache_returns_without_calling_llm(self, tmp_path):
        cache = FileCache(root=tmp_path / "cache")
        t = Translator(cache=cache, provider="openai", api_key="x")
        from koreanpulse.cache import cache_key
        key = cache_key("corp_name", "openai", "gpt-5-mini", "삼성전자")
        await cache.set(key, "Samsung Electronics")
        out = await t.translate_corp_name("삼성전자")
        assert out == "Samsung Electronics"

    @pytest.mark.asyncio
    async def test_separate_cache_namespace_from_title(self, tmp_path):
        """Same Korean text in `translate_corp_name` and `translate_ko_to_en`
        must not collide — distinct cache keys."""
        from koreanpulse.cache import cache_key
        title_key = cache_key("translate", "openai", "gpt-5-mini", "삼성전자")
        corp_key = cache_key("corp_name", "openai", "gpt-5-mini", "삼성전자")
        assert title_key != corp_key


class TestHostedMode:
    """KOREANPULSE_CACHE_MODE=hosted — Worker dispatch path."""

    HOSTED_URL = "https://cache.test.example"

    @staticmethod
    def _mock_client(handler):
        """Build an httpx.AsyncClient backed by a MockTransport."""
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=5.0)

    def test_default_mode_is_local(self, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_CACHE_MODE", raising=False)
        t = Translator(provider="openai", api_key="x")
        assert t.mode == "local"

    def test_env_selects_hosted_mode(self, monkeypatch):
        monkeypatch.setenv("KOREANPULSE_CACHE_MODE", "hosted")
        monkeypatch.setenv("KOREANPULSE_LICENSE_KEY", "kp_envkey")
        t = Translator(provider="openai", api_key="x")
        assert t.mode == "hosted"
        assert t._license_key == "kp_envkey"

    def test_unknown_mode_raises(self):
        with pytest.raises(TranslationError, match="KOREANPULSE_CACHE_MODE"):
            Translator(mode="weird", api_key="x")

    @pytest.mark.asyncio
    async def test_hosted_without_license_key_raises(self, monkeypatch):
        monkeypatch.delenv("KOREANPULSE_LICENSE_KEY", raising=False)
        t = Translator(mode="hosted", cache_url=self.HOSTED_URL, api_key="x")
        with pytest.raises(TranslationError, match="KOREANPULSE_LICENSE_KEY missing"):
            await t.translate_ko_to_en("삼성전자")

    @pytest.mark.asyncio
    async def test_hosted_translate_posts_to_worker(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={
                "output": "Samsung Electronics", "cached": True,
                "provider": "openai", "model": "gpt-5-mini",
            })

        async with self._mock_client(handler) as client:
            t = Translator(
                mode="hosted", cache_url=self.HOSTED_URL,
                license_key="kp_test123", api_key="x", http_client=client,
            )
            out = await t.translate_ko_to_en("삼성전자")

        assert out == "Samsung Electronics"
        assert seen["url"].endswith("/v1/translate")
        assert seen["body"]["license_key"] == "kp_test123"
        assert seen["body"]["kind"] == "translate"
        assert seen["body"]["text"] == "삼성전자"

    @pytest.mark.asyncio
    async def test_hosted_summarize_includes_attribution(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={
                "output": "Summary text", "cached": False,
                "provider": "openai", "model": "gpt-5-mini",
            })

        async with self._mock_client(handler) as client:
            t = Translator(
                mode="hosted", cache_url=self.HOSTED_URL,
                license_key="kp_test456", api_key="x", http_client=client,
            )
            out = await t.summarize_ko("긴 한국어 문서", attribution="DART")

        assert out == "Summary text"
        assert seen["body"]["kind"] == "summarize"
        assert seen["body"]["attribution"] == "DART"

    @pytest.mark.asyncio
    async def test_hosted_402_raises_immediately(self):
        """No fallback to local on Worker failure — paid value must be visible."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(402, json={"error": "license invalid"})

        async with self._mock_client(handler) as client:
            t = Translator(
                mode="hosted", cache_url=self.HOSTED_URL,
                license_key="kp_revoked", api_key="x", http_client=client,
            )
            with pytest.raises(TranslationError, match="hosted cache failed"):
                await t.translate_ko_to_en("삼성전자")

    @pytest.mark.asyncio
    async def test_hosted_skips_local_cache(self, tmp_path):
        """Hosted mode must NOT consult the local FileCache — the Worker
        already cached at the network edge and a stale local layer would
        cause silent divergence."""
        from koreanpulse.cache import cache_key
        cache = FileCache(root=tmp_path / "cache")
        # Pre-seed local cache with what would be a hit in local mode
        key = cache_key("translate", "openai", "gpt-5-mini", "삼성전자")
        await cache.set(key, "STALE_LOCAL_VALUE")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "output": "FRESH_WORKER_VALUE", "cached": False,
                "provider": "openai", "model": "gpt-5-mini",
            })

        async with self._mock_client(handler) as client:
            t = Translator(
                cache=cache, mode="hosted", cache_url=self.HOSTED_URL,
                license_key="kp_test", api_key="x", http_client=client,
            )
            out = await t.translate_ko_to_en("삼성전자")

        assert out == "FRESH_WORKER_VALUE"  # not the stale local value


class TestLocalProviderTransportErrors:
    """When the live provider call fails on every retry, retry_async re-raises
    the raw httpx exception. The translate layer must convert it into a typed
    TranslationError (not leak a raw httpx.HTTPError). Fixtures are synthetic
    MockTransport handlers — no real OpenAI / Anthropic call.

    Non-retryable statuses (401) / errors ("connection refused") are used so
    retry_async fails fast without real backoff sleeps.
    """

    @staticmethod
    def _patch_client(monkeypatch, handler):
        real = httpx.AsyncClient

        def factory(*args, **kwargs):
            return real(transport=httpx.MockTransport(handler), timeout=5.0)

        monkeypatch.setattr("koreanpulse.translate.httpx.AsyncClient", factory)

    @pytest.mark.asyncio
    async def test_openai_http_error_wrapped(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid api key"})

        self._patch_client(monkeypatch, handler)
        t = Translator(provider="openai", api_key="bad", mode="local")
        with pytest.raises(TranslationError, match="OpenAI API returned HTTP 401"):
            await t.translate_ko_to_en("삼성전자 실적 발표")

    @pytest.mark.asyncio
    async def test_openai_network_error_wrapped(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        self._patch_client(monkeypatch, handler)
        t = Translator(provider="openai", api_key="x", mode="local")
        with pytest.raises(TranslationError, match="OpenAI API request failed"):
            await t.translate_ko_to_en("삼성전자 실적 발표")

    @pytest.mark.asyncio
    async def test_anthropic_http_error_wrapped(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "invalid api key"})

        self._patch_client(monkeypatch, handler)
        t = Translator(provider="anthropic", api_key="bad", mode="local")
        with pytest.raises(TranslationError, match="Anthropic API returned HTTP 401"):
            await t.translate_ko_to_en("삼성전자 실적 발표")

    @pytest.mark.asyncio
    async def test_wrapped_error_is_not_httpx_exception(self, monkeypatch):
        """A caller catching TranslationError must not have to also know httpx."""
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "nope"})

        self._patch_client(monkeypatch, handler)
        t = Translator(provider="openai", api_key="bad", mode="local")
        with pytest.raises(TranslationError) as excinfo:
            await t.translate_ko_to_en("테스트")
        assert not isinstance(excinfo.value, httpx.HTTPError)
