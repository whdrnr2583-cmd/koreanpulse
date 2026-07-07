"""License-key gate for paid tiers.

This is the v0 in-memory implementation. License issuance happens in the
Cloudflare Worker (`webhook-worker/`) via Polar (sole billing provider,
active since 2026-05-06). The D1 store is the production source of truth;
this in-memory store is used by tests and as the legacy LicenseStore
Protocol reference. The Lemon Squeezy store application was declined
2026-05-06; LS code paths remain in `koreanpulse.billing/` only as
historical reference.

Each MCP tool that costs money calls `validate_license_or_raise(license_key)`
at the top. The MCP client passes the key as a tool arg or via a connection
header (depending on transport).
"""
from __future__ import annotations

import asyncio
import enum
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class Plan(str, enum.Enum):
    """Pricing v2 (2026-05-05): workflow-priced 3-tier ladder.

    Active plans:
      SOLO       — $29/mo, individual traders / solo analysts
      ANALYST    — $79/mo, the real revenue tier (boutique fund analysts)
      DESK       — $249/mo, small research teams (3 seats)

    Deprecated (back-compat only — historical license rows / webhook
    payloads). All deprecated plans behave like SOLO at the limits layer:
      FREE / STARTER / INDIE / PRO / ENTERPRISE
    """
    # Active 2026-05-05+
    SOLO = "solo"
    ANALYST = "analyst"
    DESK = "desk"
    # Deprecated aliases — kept so old DB rows resolve, never issued anew.
    FREE = "free"
    STARTER = "starter"
    INDIE = "indie"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# Pricing in USD/month. Annual billing gets -20% (handled at billing layer).
# Workflow-priced ladder. Free Public Web (`/today`) is access-controlled at
# the worker layer (no license required) so it does not appear here.
PLAN_PRICING_USD: dict[Plan, int] = {
    Plan.SOLO: 29,
    Plan.ANALYST: 79,
    Plan.DESK: 249,
    # ── deprecated (alias-priced to Solo so existing rows don't break) ───
    Plan.FREE: 0,
    Plan.STARTER: 29,
    Plan.INDIE: 29,
    Plan.PRO: 29,
    Plan.ENTERPRISE: 29,
}


# Plan limits for hosted Cloud tiers. Values match the customer-surface
# pricing table maintained in landing/README/listings.
#
# Free Public Web (/today, /today.json) is unauthenticated and does not
# appear here — it has no license object. The deprecated FREE plan below
# applies only to historical license rows (treated as Solo limits).
PLAN_LIMITS: dict[Plan, dict] = {
    Plan.SOLO: {
        "calls_per_month": 2_000,
        "watchlists": 5,
        "retention_days": 30,
        "alert_channels": 1,
        "seats": 1,
    },
    Plan.ANALYST: {
        "calls_per_month": 15_000,
        "watchlists": 25,
        "retention_days": 365,
        "alert_channels": 3,
        "seats": 1,
    },
    Plan.DESK: {
        "calls_per_month": 100_000,
        "watchlists": 100,
        "retention_days": 365,
        "alert_channels": 5,
        "seats": 3,
    },
    # ── deprecated aliases — mirror Solo limits for back-compat ──────────
    Plan.FREE:       {"calls_per_month": 2_000, "watchlists": 5, "retention_days": 30, "alert_channels": 1, "seats": 1},
    Plan.STARTER:    {"calls_per_month": 2_000, "watchlists": 5, "retention_days": 30, "alert_channels": 1, "seats": 1},
    Plan.INDIE:      {"calls_per_month": 2_000, "watchlists": 5, "retention_days": 30, "alert_channels": 1, "seats": 1},
    Plan.PRO:        {"calls_per_month": 2_000, "watchlists": 5, "retention_days": 30, "alert_channels": 1, "seats": 1},
    Plan.ENTERPRISE: {"calls_per_month": 2_000, "watchlists": 5, "retention_days": 30, "alert_channels": 1, "seats": 1},
}


# Design Partner Lifetime: first 20 named seats pay $299+ once, get Analyst
# tier forever. This is intentionally NOT promoted on landing or
# marketplace listings — only mentioned as a contact-only footnote in
# README and one or two operator docs.
LIFETIME_DEAL_PRICE_USD = 299
LIFETIME_DEAL_MAX_SEATS = 20
LIFETIME_DEAL_PLAN = Plan.ANALYST


class LicenseError(Exception):
    """Raised when a license is missing, invalid, expired, or over quota."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code  # e.g. "missing", "invalid", "expired", "quota_exceeded"


@dataclass
class License:
    key: str
    plan: Plan
    customer_email: str
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_calls: int = 0     # rolling counter, reset monthly by webhook
    period_started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)


class LicenseStore(Protocol):
    async def get(self, key: str) -> Optional[License]: ...
    async def save(self, lic: License) -> None: ...
    async def increment_usage(self, key: str, n: int = 1) -> int: ...
    async def find_by_email(self, email: str) -> Optional[License]: ...
    async def next_lifetime_seq(self) -> int: ...


class InMemoryLicenseStore:
    """Single-process store. Swap to Postgres for prod."""

    def __init__(self) -> None:
        self._data: dict[str, License] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[License]:
        async with self._lock:
            return self._data.get(key)

    async def save(self, lic: License) -> None:
        async with self._lock:
            self._data[lic.key] = lic

    async def increment_usage(self, key: str, n: int = 1) -> int:
        async with self._lock:
            lic = self._data.get(key)
            if lic is None:
                raise LicenseError("invalid", f"license key not found: {key[:8]}…")
            lic.period_calls += n
            return lic.period_calls

    async def find_by_email(self, email: str) -> Optional[License]:
        """Return the most recently-created license matching `email` (case-insensitive)."""
        target = email.lower()
        async with self._lock:
            matches = [
                lic for lic in self._data.values()
                if lic.customer_email.lower() == target
            ]
        if not matches:
            return None
        matches.sort(key=lambda lic: lic.created_at, reverse=True)
        return matches[0]

    async def next_lifetime_seq(self) -> int:
        """Next 1-indexed deal_seq for a new lifetime license."""
        async with self._lock:
            used = [
                lic.metadata.get("deal_seq", 0)
                for lic in self._data.values()
                if is_lifetime(lic)
            ]
        return (max(used) if used else 0) + 1


def issue_license_key() -> str:
    """Generate a fresh url-safe license key (32 bytes ≈ 256 bits)."""
    return f"kp_{secrets.token_urlsafe(32)}"


def is_lifetime(lic: License) -> bool:
    """True if the license was issued under the lifetime deal."""
    return bool(lic.metadata.get("lifetime"))


def issue_lifetime_license(
    *,
    customer_email: str,
    deal_seq: int,
    plan: Plan = LIFETIME_DEAL_PLAN,
) -> License:
    """Mint a lifetime-deal license. Caller is responsible for verifying payment."""
    if deal_seq < 1 or deal_seq > LIFETIME_DEAL_MAX_SEATS:
        raise ValueError(
            f"deal_seq must be in 1..{LIFETIME_DEAL_MAX_SEATS}, got {deal_seq}"
        )
    return License(
        key=issue_license_key(),
        plan=plan,
        customer_email=customer_email,
        active=True,
        metadata={
            "lifetime": True,
            "deal_seq": deal_seq,
            "deal_price_usd": LIFETIME_DEAL_PRICE_USD,
        },
    )


_default_store: Optional[LicenseStore] = None
_setup_lock = asyncio.Lock()


def set_default_store(store: LicenseStore) -> None:
    """Wire the process-wide default store (call once at startup)."""
    global _default_store
    _default_store = store


def get_default_store() -> LicenseStore:
    """Sync default-store getter. Returns InMemory fallback if nothing wired.

    Prefer `aget_default_store()` in production paths so Postgres autoconnect
    can run when `DATABASE_URL` is set.
    """
    global _default_store
    if _default_store is None:
        _default_store = InMemoryLicenseStore()
    return _default_store


async def aget_default_store() -> LicenseStore:
    """Async default-store getter with first-call setup.

    Setup rules (first call only, guarded by lock):
      1. If `set_default_store()` already wired one → return it.
      2. If `DATABASE_URL` is set → autoconnect `PostgresLicenseStore`.
      3. If `KOREANPULSE_REQUIRE_LICENSE=1` and Postgres unavailable →
         raise `LicenseError("config")`. Production requires Postgres so
         the webhook process and the MCP server share one license table.
      4. Otherwise (dev) → fall back to `InMemoryLicenseStore`.
    """
    global _default_store
    if _default_store is not None:
        return _default_store
    async with _setup_lock:
        if _default_store is not None:
            return _default_store
        require = os.environ.get("KOREANPULSE_REQUIRE_LICENSE", "0").strip() == "1"
        dsn = os.environ.get("DATABASE_URL", "").strip()
        if dsn:
            try:
                from koreanpulse.license_postgres import PostgresLicenseStore
                _default_store = await PostgresLicenseStore.connect(dsn)
                logger.info("license: PostgresLicenseStore connected")
                return _default_store
            except Exception as exc:  # noqa: BLE001
                if require:
                    raise LicenseError(
                        "config",
                        f"DATABASE_URL set but Postgres connect failed: {exc}",
                    ) from exc
                logger.warning(
                    "license: postgres connect failed, falling back to in-memory: %s",
                    exc,
                )
        if require:
            raise LicenseError(
                "config",
                "KOREANPULSE_REQUIRE_LICENSE=1 but DATABASE_URL not set. "
                "Production needs Postgres so the webhook process and MCP "
                "server share the same license store. "
                "See docs/POSTGRES.md.",
            )
        _default_store = InMemoryLicenseStore()
        logger.info("license: InMemoryLicenseStore (dev mode)")
        return _default_store


async def _validate_via_webhook(
    license_key: str,
    validate_url: str,
    shared_secret: str,
    cost_units: int,
) -> License:
    """Validate + charge against webhook-worker /v1/validate (D1 source of truth).

    Hosted MCP path: webhook-worker is the only process that writes to D1
    when Polar issues a license, so the only correct way for the Python
    `paid_gate` to validate that key is to ask the same Worker over HTTP.
    Authentication mirrors cache-worker: HMAC-SHA256 over the JSON body
    using KOREANPULSE_CACHE_SHARED_SECRET, sent in `X-Cache-Signature`.

    Response contract (webhook-worker/src/license.ts validateAndCharge):
      success: { ok: true,  plan: "solo"|"analyst"|"desk", period_calls: <int> }
      failure: { ok: false, code: "missing"|"invalid"|"inactive"|"quota_exceeded", reason: <str> }

    Raises LicenseError with the same code semantics as the in-process path.
    """
    import hashlib
    import hmac
    import json as _json
    import httpx

    body = _json.dumps({"license_key": license_key.strip()}, separators=(",", ":"))
    signature = hmac.new(
        shared_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                validate_url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Cache-Signature": signature,
                },
            )
    except (httpx.HTTPError, OSError) as exc:
        raise LicenseError(
            "config",
            f"webhook validate transport failed ({validate_url}): {exc}",
        ) from exc

    if resp.status_code != 200:
        raise LicenseError(
            "config",
            f"webhook validate returned HTTP {resp.status_code}: {resp.text[:200]}",
        )

    try:
        result = resp.json()
    except ValueError as exc:
        raise LicenseError(
            "config",
            f"webhook validate returned non-JSON: {resp.text[:200]}",
        ) from exc

    if not result.get("ok"):
        code = result.get("code", "invalid")
        reason = result.get("reason", "license invalid")
        raise LicenseError(code, reason)

    plan_str = result.get("plan", "solo")
    try:
        plan = Plan(plan_str)
    except ValueError:
        # Unknown plan from webhook — treat as invalid rather than crash.
        raise LicenseError("invalid", f"unknown plan from webhook: {plan_str}")

    # Build a partial License object — webhook path doesn't surface
    # email/created_at/metadata but callers (paid_gate) only read .plan
    # and .key, and the webhook already charged usage so we set the
    # returned period_calls to whatever the webhook reports.
    return License(
        key=license_key.strip(),
        plan=plan,
        customer_email="",
        active=True,
        period_calls=int(result.get("period_calls", 0)),
        metadata={"source": "webhook_validate", "cost_units": cost_units},
    )


async def validate_license_or_raise(
    license_key: Optional[str],
    *,
    store: Optional[LicenseStore] = None,
    cost_units: int = 1,
) -> License:
    """Validate the key, charge `cost_units` calls against the period counter.

    Resolution order:
      1. If KOREANPULSE_VALIDATE_URL + KOREANPULSE_CACHE_SHARED_SECRET set
         → HTTP-validate against webhook-worker (D1 source of truth).
         This is the production path on the hosted MCP — D1 is the only
         license store that the Polar webhook writes to.
      2. Else if `store` arg passed (or default store wired) → in-process
         (Postgres if DATABASE_URL, InMemory otherwise). Used by BYOK
         self-host and unit tests.

    Raises:
        LicenseError("missing"|"invalid"|"inactive"|"quota_exceeded"|"config")
    """
    if not license_key:
        raise LicenseError(
            "missing",
            "Missing license key.",
        )

    # (1) Hosted webhook validate path — D1 source of truth.
    validate_url = os.environ.get("KOREANPULSE_VALIDATE_URL", "").strip()
    shared_secret = os.environ.get("KOREANPULSE_CACHE_SHARED_SECRET", "").strip()
    if validate_url and shared_secret:
        return await _validate_via_webhook(
            license_key, validate_url, shared_secret, cost_units
        )

    # (2) In-process store path — Postgres for self-host with DATABASE_URL,
    # InMemory for dev/tests. Same semantics as before this commit.
    store = store or await aget_default_store()
    lic = await store.get(license_key)
    if lic is None:
        raise LicenseError("invalid", "Invalid license key.")
    if not lic.active:
        raise LicenseError(
            "inactive",
            f"License inactive (plan={lic.plan.value}). Your license has expired.",
        )

    limits = PLAN_LIMITS[lic.plan]
    monthly = limits["calls_per_month"]
    if monthly != -1 and lic.period_calls + cost_units > monthly:
        raise LicenseError(
            "quota_exceeded",
            f"Quota exceeded for plan={lic.plan.value} ({lic.period_calls}/{monthly}). Upgrade or wait.",
        )

    new_total = await store.increment_usage(license_key, n=cost_units)
    logger.debug("license: %s plan=%s usage=%d", license_key[:8], lic.plan.value, new_total)
    return lic
