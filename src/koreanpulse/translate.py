"""Korean→English translation + light summarization.

Server-side LLM. We pay for the call, the cache absorbs the cost across all
tenants. Same Korean filing title gets translated once, then served from
cache ~forever.

## Why server-side instead of letting the client LLM do it
- Cache hit rate 80%+ → real margin
- Deterministic value-add (the product's core promise)
- Consistent quality across tenants

Anything beyond translation + ≤200-word summary stays on the *client* LLM
(see SPEC.md for the split). This module deliberately doesn't do analysis,
synthesis, or Q&A — those are the client's job.

## Provider selection (default: OpenAI GPT-5-mini)

| Provider | Model | $/M in | $/M out | Why |
|---|---|---|---|---|
| **openai** *(default)* | gpt-5-mini | $0.25 | $2.00 | cheapest of the capable tier, ~3× cheaper than Haiku |
| anthropic | claude-haiku-4-5-20251001 | $1.00 | $5.00 | fallback if OpenAI key absent or quality regression detected |

Switch via env: `KOREANPULSE_TRANSLATE_PROVIDER=anthropic` or per-Translator
constructor arg.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from agentprod import (
    CostTracker,
    ModelPricing,
    Throttle,
    retry_async,
)

from koreanpulse.cache import Cache, NullCache, cache_key

logger = logging.getLogger(__name__)


# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_PROVIDER = os.environ.get("KOREANPULSE_TRANSLATE_PROVIDER", "openai").lower()
DEFAULT_MAX_INPUT_CHARS = 6000  # truncate beyond this; long filings get partial summary

# BYOK ("local") vs Hosted cache mode. Set via KOREANPULSE_CACHE_MODE.
#   local  — call OpenAI/Anthropic directly, store results in FileCache.
#            Suitable for free / BYOK users with their own provider key.
#   hosted — call koreanpulse-cache Worker (/v1/translate). The Worker holds
#            our OpenAI key, fronts a global KV cache, and validates the
#            license before responding. No local cache used (the Worker
#            already cached at the network edge).
DEFAULT_CACHE_MODE = "local"
DEFAULT_HOSTED_URL = "https://cache.koreanpulse.dev"

# Per-provider default model + pricing. Refresh quarterly.
# Note: `KOREANPULSE_TRANSLATE_MODEL` env override is applied in __init__,
# but ONLY for the default provider — otherwise asking for `provider="anthropic"`
# could accidentally pick up a gpt-* model name from env.
PROVIDER_DEFAULTS: dict[str, dict] = {
    "openai": {
        "model": "gpt-5-mini",
        "pricing": ModelPricing(input_per_1k=0.00025, output_per_1k=0.002),
        "api_base": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "model": "claude-haiku-4-5-20251001",
        "pricing": ModelPricing(input_per_1k=0.001, output_per_1k=0.005),
        "api_base": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
    },
}

# One bucket per process. Both providers' rate limits are higher than this.
_throttle = Throttle(capacity=20, refill_per_sec=20, jitter_ms=(5, 25))


# ── Prompts (provider-agnostic) ─────────────────────────────────────────────

_TRANSLATE_SYSTEM = (
    "You are a precise translator of Korean financial / industry text into "
    "English. Translate faithfully. Preserve company names in their official "
    "English form when widely known (e.g. '삼성전자' → 'Samsung Electronics'); "
    "otherwise transliterate and append the Korean in parentheses on first use. "
    "Output the translation only, no commentary."
)

_SUMMARIZE_SYSTEM = (
    "You are a precise financial-industry analyst writing for English-speaking "
    "fund analysts. Summarize the Korean text in <=200 English words. "
    "Lead with the single most material fact. Preserve numbers exactly. "
    "If a number is ambiguous (KRW vs USD, billions vs millions), say so. "
    "End with one line: 'Source: <attribution>'. No commentary beyond the summary."
)

_CORP_NAME_SYSTEM = (
    "Return the official English name of the Korean company. "
    "For widely-known Korean companies, use the standard form "
    "(examples: '삼성전자' → 'Samsung Electronics', '셀트리온' → 'Celltrion', "
    "'SK하이닉스' → 'SK Hynix', '네이버' → 'NAVER', '카카오' → 'Kakao', "
    "'LG에너지솔루션' → 'LG Energy Solution', 'HD현대중공업' → 'HD Hyundai Heavy Industries'). "
    "For lesser-known names, transliterate (Romanize) without parentheses or quotes. "
    "Output the company name only — no commentary, no punctuation, no Korean."
)


class TranslationError(RuntimeError):
    pass


class Translator:
    """Cached server-side translator + summarizer with pluggable LLM provider.

    Args:
        cache: backing cache. Use NullCache to disable.
        cost_tracker: optional, for per-tenant cost accounting.
        provider: "openai" or "anthropic". Defaults to KOREANPULSE_TRANSLATE_PROVIDER
            env (default "openai").
        model: model id for the chosen provider. Defaults to provider's default.
        api_key: API key. Falls back to {OPENAI,ANTHROPIC}_API_KEY env.
        pricing: ModelPricing for cost tracking. Defaults to provider's default.
        mode: "local" (BYOK, default) or "hosted" (call koreanpulse-cache Worker).
            Falls back to KOREANPULSE_CACHE_MODE env.
        cache_url: hosted Worker base URL (no trailing slash).
            Falls back to KOREANPULSE_CACHE_URL env, then DEFAULT_HOSTED_URL.
        license_key: hosted-mode subscription key.
            Falls back to KOREANPULSE_LICENSE_KEY env. Required when mode='hosted'.
    """

    def __init__(
        self,
        cache: Optional[Cache] = None,
        cost_tracker: Optional[CostTracker] = None,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        pricing: Optional[ModelPricing] = None,
        mode: Optional[str] = None,
        cache_url: Optional[str] = None,
        license_key: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._cache = cache or NullCache()
        self._cost = cost_tracker

        prov = (provider or DEFAULT_PROVIDER).lower()
        if prov not in PROVIDER_DEFAULTS:
            raise TranslationError(
                f"unknown provider: {prov!r}. choose one of {list(PROVIDER_DEFAULTS)}"
            )
        defaults = PROVIDER_DEFAULTS[prov]
        self._provider = prov

        # Model resolution: explicit > env (only when active provider matches
        # the env-configured default provider) > per-provider default.
        # This guards against `provider='anthropic'` picking up a gpt-* model.
        env_model = os.environ.get("KOREANPULSE_TRANSLATE_MODEL", "").strip()
        if model:
            self._model = model
        elif env_model and prov == DEFAULT_PROVIDER:
            self._model = env_model
        else:
            self._model = defaults["model"]

        self._pricing = pricing or defaults["pricing"]
        self._api_base = defaults["api_base"]
        self._api_key = api_key or os.environ.get(defaults["env_key"], "")

        # BYOK vs Hosted dispatch.
        env_mode = os.environ.get("KOREANPULSE_CACHE_MODE", "").strip().lower()
        self._mode = (mode or env_mode or DEFAULT_CACHE_MODE).lower()
        if self._mode not in ("local", "hosted"):
            raise TranslationError(
                f"unknown KOREANPULSE_CACHE_MODE={self._mode!r}; expected 'local' or 'hosted'"
            )
        env_cache_url = os.environ.get("KOREANPULSE_CACHE_URL", "").strip()
        self._cache_url = (cache_url or env_cache_url or DEFAULT_HOSTED_URL).rstrip("/")
        self._license_key = (
            license_key or os.environ.get("KOREANPULSE_LICENSE_KEY", "")
        ).strip()
        # Optional injected client — used by tests to attach an MockTransport.
        # In production we lazily create one per call.
        self._http_client = http_client

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def mode(self) -> str:
        return self._mode

    async def translate_ko_to_en(
        self,
        text: str,
        *,
        labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Translate Korean text to English. Cached per (provider, model, text)."""
        if not text or not text.strip():
            return ""

        if self._mode == "hosted":
            # Hosted Worker fronts a global KV cache and our OpenAI key.
            # We don't keep a second local cache layer — the Worker already
            # cached the result and bouncing through a local file would just
            # add stale-key risk on model swaps.
            return await self._call_hosted(kind="translate", text=text)

        # Provider in cache key so swapping models doesn't poison cache.
        key = cache_key("translate", self._provider, self._model, text)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        out = await self._call_llm(
            system=_TRANSLATE_SYSTEM,
            user=text[:DEFAULT_MAX_INPUT_CHARS],
            max_tokens=1024,
            labels={**(labels or {}), "op": "translate"},
        )
        await self._cache.set(key, out)
        return out

    async def translate_corp_name(
        self,
        name_ko: str,
        *,
        labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Translate a Korean company name to its English form.

        Separate from `translate_ko_to_en` so:
          - the system prompt is tuned for short, single-line company names
            (no parenthetical Korean appendix);
          - the cache key namespace is distinct from filing-title cache, so
            "삼성전자" the company name and "삼성전자" inside a filing title
            don't collide.

        Same hosted-mode behaviour: in `KOREANPULSE_CACHE_MODE=hosted` the
        Worker handles caching and returns the result; in local mode we
        cache locally.
        """
        if not name_ko or not name_ko.strip():
            return ""

        if self._mode == "hosted":
            return await self._call_hosted(kind="translate", text=name_ko)

        key = cache_key("corp_name", self._provider, self._model, name_ko)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        out = await self._call_llm(
            system=_CORP_NAME_SYSTEM,
            user=name_ko[:DEFAULT_MAX_INPUT_CHARS],
            max_tokens=128,
            labels={**(labels or {}), "op": "translate_corp_name"},
        )
        await self._cache.set(key, out)
        return out

    async def summarize_ko(
        self,
        text: str,
        *,
        attribution: str,
        labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Summarize Korean text in ≤200 English words. Cached per (provider, model, text)."""
        if not text or not text.strip():
            return ""

        if self._mode == "hosted":
            return await self._call_hosted(
                kind="summarize", text=text, attribution=attribution
            )

        key = cache_key("summarize", self._provider, self._model, text)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        prompt = f"{text[:DEFAULT_MAX_INPUT_CHARS]}\n\n---\nAttribution: {attribution}"
        out = await self._call_llm(
            system=_SUMMARIZE_SYSTEM,
            user=prompt,
            max_tokens=512,
            labels={**(labels or {}), "op": "summarize"},
        )
        await self._cache.set(key, out)
        return out

    # ── Hosted Worker dispatch ─────────────────────────────────────────────

    async def _call_hosted(
        self,
        *,
        kind: str,
        text: str,
        attribution: str = "",
    ) -> str:
        """POST to koreanpulse-cache `/v1/translate`. No fallback on failure.

        Hosted-mode value (global cache hit + our OpenAI key) only matters
        if we keep the surface honest — falling back to BYOK on a Worker
        outage would mask the value to paying customers and create silent
        billing-vs-quality drift. Raise immediately and let the caller
        decide (typically: switch KOREANPULSE_CACHE_MODE=local).
        """
        if not self._license_key:
            raise TranslationError(
                "KOREANPULSE_LICENSE_KEY missing — required for "
                "KOREANPULSE_CACHE_MODE=hosted. Set "
                "KOREANPULSE_CACHE_MODE=local for BYOK."
            )

        payload: dict[str, Any] = {
            "kind": kind,
            "text": text[:DEFAULT_MAX_INPUT_CHARS],
            "license_key": self._license_key,
        }
        if kind == "summarize":
            payload["attribution"] = attribution

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=30.0)
        try:
            async def _call() -> httpx.Response:
                return await client.post(
                    f"{self._cache_url}/v1/translate", json=payload
                )

            resp = await retry_async(_call, max_attempts=3, base_seconds=1.0)
        finally:
            if owns_client:
                await client.aclose()
        if resp.status_code != 200:
            try:
                err = resp.json().get("error", "unknown")
            except (ValueError, AttributeError):
                err = (resp.text or "")[:200]
            # Logged with key prefix only — never the full secret.
            logger.warning(
                "hosted cache returned %s for license=%s…: %s",
                resp.status_code,
                self._license_key[:8],
                err,
            )
            raise TranslationError(
                f"hosted cache failed ({resp.status_code}): {err}. "
                f"Check KOREANPULSE_LICENSE_KEY or set "
                f"KOREANPULSE_CACHE_MODE=local for BYOK."
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise TranslationError(f"hosted cache returned non-JSON: {exc}") from exc
        return str(data.get("output", "")).strip()

    # ── Provider dispatch ──────────────────────────────────────────────────

    async def _call_llm(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        labels: dict[str, str],
    ) -> str:
        if not self._api_key:
            env_var = PROVIDER_DEFAULTS[self._provider]["env_key"]
            raise TranslationError(
                f"{env_var} missing. Set it to enable server-side translation, "
                f"or change provider via KOREANPULSE_TRANSLATE_PROVIDER."
            )

        await _throttle.acquire(timeout=2.0, label=f"{self._provider}:{labels.get('op','?')}")

        if self._provider == "openai":
            return await self._call_openai(
                system=system, user=user, max_tokens=max_tokens, labels=labels
            )
        if self._provider == "anthropic":
            return await self._call_anthropic(
                system=system, user=user, max_tokens=max_tokens, labels=labels
            )
        raise TranslationError(f"unsupported provider: {self._provider}")

    async def _call_openai(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        labels: dict[str, str],
    ) -> str:
        async def _call() -> dict:
            payload: dict = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                # GPT-5 series uses max_completion_tokens, not max_tokens.
                "max_completion_tokens": max_tokens,
            }
            # Match cache-worker hardening: gpt-5* burns the entire budget on
            # internal reasoning when reasoning_effort defaults to "high",
            # leaving content="". Force minimal so translation tokens reach
            # output. See feedback_cf_worker_openai_gateway.md.
            if self._model.startswith("gpt-5"):
                payload["reasoning_effort"] = "minimal"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()

        data = await retry_async(_call, max_attempts=3, base_seconds=1.0)

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationError(f"unexpected OpenAI response shape: {exc}") from exc

        # gpt-5 family can return finish_reason="length" with content="" when
        # reasoning consumed the budget. Treat that as a translation failure
        # so callers can retry / fall back instead of silently caching "".
        if not (text or "").strip():
            finish = (data.get("choices") or [{}])[0].get("finish_reason", "")
            usage = data.get("usage") or {}
            raise TranslationError(
                f"empty content from {self._model} "
                f"(finish_reason={finish}, usage={usage})"
            )

        if self._cost is not None:
            usage = data.get("usage", {})
            # OpenAI sometimes nests cached tokens under prompt_tokens_details
            details = usage.get("prompt_tokens_details") or {}
            self._cost.record(
                model=self._model,
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                cached_input_tokens=int(details.get("cached_tokens", 0)),
                pricing=self._pricing,
                labels={**labels, "provider": "openai"},
            )

        return (text or "").strip()

    async def _call_anthropic(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        labels: dict[str, str],
    ) -> str:
        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._api_base}/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "max_tokens": max_tokens,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                resp.raise_for_status()
                return resp.json()

        data = await retry_async(_call, max_attempts=3, base_seconds=1.0)

        try:
            content_blocks = data.get("content", [])
            text = "".join(
                b.get("text", "") for b in content_blocks if b.get("type") == "text"
            )
        except (KeyError, AttributeError) as exc:
            raise TranslationError(f"unexpected Anthropic response shape: {exc}") from exc

        if self._cost is not None:
            usage = data.get("usage", {})
            self._cost.record(
                model=self._model,
                input_tokens=int(usage.get("input_tokens", 0)),
                output_tokens=int(usage.get("output_tokens", 0)),
                pricing=self._pricing,
                labels={**labels, "provider": "anthropic"},
            )

        return text.strip()
