"""Lemon Squeezy webhook handling — signature verification + event dispatch.

Lemon Squeezy is the Merchant of Record we use for global billing (handles
VAT, sales tax, GDPR data processing). They POST a JSON payload to our
webhook endpoint with an `X-Signature` header containing an HMAC-SHA256 of
the raw body computed with our `LEMONSQUEEZY_WEBHOOK_SECRET`.

Why we picked LS over Stripe for v0:
  - MoR — they handle Korean tax filing for us (avoids 사업자등록 + 부가세
    headaches in the early stage).
  - 5% + processing — predictable, no 1099-K, no Stripe Atlas trap.
  - Korean indie founders can sign up directly without US LLC.

Variant ID → Plan mapping is loaded from env so the same code works in
test/live storefronts. See `.env.example` for `LEMONSQUEEZY_VARIANT_*`.

Reference: <https://docs.lemonsqueezy.com/help/webhooks>
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from koreanpulse.license import (
    LIFETIME_DEAL_PLAN,
    License,
    LicenseStore,
    Plan,
    aget_default_store,
    is_lifetime,
    issue_license_key,
)

logger = logging.getLogger(__name__)


# ── Variant ID → Plan ──────────────────────────────────────────────────────
# In Lemon Squeezy you create one Variant per pricing tier.
# Register their numeric IDs here via env so the same handler works in
# test mode and live mode without code changes.
#
# Pricing v2 (2026-05-05): Workflow-priced 3-tier ladder. Required in
# production: SOLO + ANALYST + DESK. Deprecated slots (PRO / STARTER /
# INDIE / ENTERPRISE) remain wired for back-compat with historical
# storefronts — leave them unset in production.
def _read_variant_map() -> dict[str, Plan]:
    """Build the variant_id (str) → Plan map from env vars.

    Production requires SOLO + ANALYST + DESK. Deprecated tiers (PRO,
    STARTER, INDIE, ENTERPRISE) are kept as no-op slots for back-compat
    with historical storefronts; leave them unset and the variant map
    only contains the active 3-tier ladder.
    """
    out: dict[str, Plan] = {}
    pairs = [
        ("LEMONSQUEEZY_VARIANT_SOLO", Plan.SOLO),
        ("LEMONSQUEEZY_VARIANT_ANALYST", Plan.ANALYST),
        ("LEMONSQUEEZY_VARIANT_DESK", Plan.DESK),
        # Deprecated — historical storefront rows. Unused in production.
        ("LEMONSQUEEZY_VARIANT_PRO", Plan.PRO),
        ("LEMONSQUEEZY_VARIANT_STARTER", Plan.STARTER),
        ("LEMONSQUEEZY_VARIANT_INDIE", Plan.INDIE),
        ("LEMONSQUEEZY_VARIANT_ENTERPRISE", Plan.ENTERPRISE),
    ]
    for env_name, plan in pairs:
        vid = os.environ.get(env_name, "").strip()
        if vid:
            out[vid] = plan
    return out


def _read_lifetime_variant() -> Optional[str]:
    return os.environ.get("LEMONSQUEEZY_VARIANT_LIFETIME", "").strip() or None


# ── Signature verification ─────────────────────────────────────────────────


class WebhookVerificationError(Exception):
    """Raised when the X-Signature header doesn't match the body HMAC."""


def verify_signature(*, body: bytes, signature_header: str, secret: str) -> bool:
    """Return True iff `signature_header` matches HMAC-SHA256(body, secret).

    Constant-time compare to defeat timing attacks.
    """
    if not signature_header or not secret:
        return False
    digest = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(digest, signature_header.strip())


# ── Idempotency ────────────────────────────────────────────────────────────
# Lemon Squeezy retries webhooks on non-2xx responses. We dedupe by
# `meta.webhook_id` to keep handler effects exactly-once.


class _SeenEvents:
    """Bounded LRU of webhook IDs we've already processed.

    In-memory only — fine until we go multi-instance. Swap to Postgres /
    Redis once we have horizontal replicas.
    """

    def __init__(self, max_size: int = 10_000) -> None:
        self._set: set[str] = set()
        self._order: list[str] = []
        self._max = max_size

    def is_new(self, webhook_id: str) -> bool:
        if webhook_id in self._set:
            return False
        self._set.add(webhook_id)
        self._order.append(webhook_id)
        if len(self._order) > self._max:
            stale = self._order.pop(0)
            self._set.discard(stale)
        return True


_seen = _SeenEvents()


# ── Event dispatch ─────────────────────────────────────────────────────────


class HandlerResult:
    """Outcome of processing one webhook event."""

    def __init__(self, *, ok: bool, action: str, license_key: Optional[str] = None,
                 message: str = "") -> None:
        self.ok = ok
        self.action = action
        self.license_key = license_key
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "license_key": self.license_key,
            "message": self.message,
        }


def _extract_email(attributes: dict) -> str:
    return (
        attributes.get("user_email")
        or attributes.get("email")
        or attributes.get("customer_email")
        or ""
    ).strip().lower()


def _extract_variant_id(attributes: dict) -> Optional[str]:
    """Pull the variant ID from a subscription or order payload."""
    if "variant_id" in attributes:
        return str(attributes["variant_id"])
    # Order payload: variant lives under first_order_item
    first = attributes.get("first_order_item") or {}
    if isinstance(first, dict) and "variant_id" in first:
        return str(first["variant_id"])
    return None


# Audience composition signal — captured at checkout via a Lemon Squeezy
# custom field labelled "role". Allowed values match landing/app/api/notify.
_ALLOWED_ROLES = {
    "analyst", "rotator", "diaspora", "journalist", "developer", "other",
}


def _extract_self_description(payload: dict, attributes: dict) -> Optional[str]:
    """Best-effort role/self-description extraction.

    Lemon Squeezy surfaces checkout custom fields in different shapes
    depending on whether the merchant defined them on the variant
    (`first_order_item.product_options.custom`) or on the storefront
    checkout (`meta.custom_data.role`). Both paths are tried; the first
    valid match wins. Unknown values normalise to "other".
    """
    candidates: list = []

    meta = payload.get("meta") or {}
    cd = meta.get("custom_data") or {}
    if isinstance(cd, dict):
        candidates.append(cd.get("role"))

    first = attributes.get("first_order_item") or {}
    if isinstance(first, dict):
        po = first.get("product_options") or {}
        if isinstance(po, dict):
            custom = po.get("custom") or {}
            if isinstance(custom, dict):
                candidates.append(custom.get("role"))

    cf = attributes.get("custom_fields_responses") or {}
    if isinstance(cf, dict):
        candidates.append(cf.get("role"))

    for c in candidates:
        if not c:
            continue
        s = str(c).strip().lower()
        if not s:
            continue
        return s if s in _ALLOWED_ROLES else "other"
    return None


async def handle_event(
    payload: dict,
    *,
    store: Optional[LicenseStore] = None,
) -> HandlerResult:
    """Dispatch one Lemon Squeezy event payload.

    Idempotent on `meta.webhook_id`. Safe to call from any FastAPI route
    after signature verification.

    Returns a HandlerResult; the route maps it to an HTTP status (always
    200 unless we want LS to retry).
    """
    store = store or await aget_default_store()

    meta = payload.get("meta", {}) or {}
    event_name = (meta.get("event_name") or "").strip()
    webhook_id = (meta.get("webhook_id") or "").strip()

    if webhook_id and not _seen.is_new(webhook_id):
        return HandlerResult(
            ok=True, action="duplicate_ignored",
            message=f"already processed webhook_id={webhook_id}",
        )

    data = payload.get("data") or {}
    attributes = data.get("attributes") or {}
    # Lemon Squeezy puts the canonical entity ID at `data.id`, not in
    # attributes. For subscription events that's the subscription_id; for
    # order_created it's the order_id. Pull it once here.
    entity_id = str(data.get("id") or "")
    email = _extract_email(attributes)
    variant_id = _extract_variant_id(attributes)
    self_description = _extract_self_description(payload, attributes)

    if event_name in ("subscription_created", "subscription_resumed"):
        return await _on_subscription_active(
            store=store, email=email, variant_id=variant_id,
            attributes=attributes, entity_id=entity_id,
            self_description=self_description,
        )

    if event_name == "subscription_updated":
        return await _on_subscription_updated(
            store=store, email=email, variant_id=variant_id, attributes=attributes,
        )

    if event_name in ("subscription_cancelled", "subscription_expired"):
        return await _on_subscription_inactive(
            store=store, email=email, attributes=attributes,
        )

    if event_name == "subscription_payment_success":
        return await _on_payment_success(
            store=store, email=email, attributes=attributes,
        )

    if event_name == "subscription_payment_failed":
        return await _on_payment_failed(
            store=store, email=email, attributes=attributes,
        )

    if event_name == "order_created":
        return await _on_order_created(
            store=store, email=email, variant_id=variant_id,
            attributes=attributes, entity_id=entity_id,
            self_description=self_description,
        )

    return HandlerResult(
        ok=True, action="ignored",
        message=f"no handler for event_name={event_name!r}",
    )


# ── Per-event handlers ─────────────────────────────────────────────────────


async def _on_subscription_active(
    *, store: LicenseStore, email: str, variant_id: Optional[str],
    attributes: dict, entity_id: str,
    self_description: Optional[str] = None,
) -> HandlerResult:
    if not email:
        return HandlerResult(ok=False, action="error", message="missing email")
    plan = _read_variant_map().get(variant_id or "")
    if plan is None:
        return HandlerResult(
            ok=False, action="error",
            message=f"unknown variant_id={variant_id!r}; configure LEMONSQUEEZY_VARIANT_* env",
        )

    # If this email already has an active license, upgrade it in place.
    existing = await store.find_by_email(email)
    if existing is not None:
        existing.plan = plan
        existing.active = True
        update: dict = {
            "ls_subscription_id": entity_id,
            "ls_variant_id": variant_id,
            "ls_status": attributes.get("status"),
        }
        # Only overwrite self_description on a fresh value — don't blank
        # out a previously-captured role on later subscription updates.
        if self_description:
            update["self_description"] = self_description
        existing.metadata.update(update)
        await store.save(existing)
        return HandlerResult(
            ok=True, action="upgraded", license_key=existing.key,
            message=f"existing license upgraded to {plan.value}",
        )

    metadata: dict = {
        "ls_subscription_id": entity_id,
        "ls_variant_id": variant_id,
        "ls_status": attributes.get("status"),
        "issued_via": "subscription_created",
    }
    if self_description:
        metadata["self_description"] = self_description

    lic = License(
        key=issue_license_key(),
        plan=plan,
        customer_email=email,
        active=True,
        metadata=metadata,
    )
    await store.save(lic)
    return HandlerResult(
        ok=True, action="issued", license_key=lic.key,
        message=f"new {plan.value} license issued for {email}",
    )


async def _on_subscription_updated(
    *, store: LicenseStore, email: str, variant_id: Optional[str], attributes: dict,
) -> HandlerResult:
    if not email:
        return HandlerResult(ok=False, action="error", message="missing email")
    lic = await store.find_by_email(email)
    if lic is None:
        # Treat as new — but we don't have the original data.id here, so
        # leave entity_id empty. subscription_created should have caught it.
        return await _on_subscription_active(
            store=store, email=email, variant_id=variant_id,
            attributes=attributes, entity_id="",
        )

    new_plan = _read_variant_map().get(variant_id or "") if variant_id else None
    if new_plan is not None and new_plan != lic.plan:
        lic.plan = new_plan
    status = attributes.get("status", "")
    lic.active = status in ("active", "on_trial", "past_due")  # past_due still serves
    lic.metadata["ls_status"] = status
    await store.save(lic)
    return HandlerResult(
        ok=True, action="updated", license_key=lic.key,
        message=f"license updated plan={lic.plan.value} active={lic.active}",
    )


async def _on_subscription_inactive(
    *, store: LicenseStore, email: str, attributes: dict,
) -> HandlerResult:
    lic = await store.find_by_email(email)
    if lic is None:
        return HandlerResult(ok=True, action="noop", message="no license to deactivate")
    # Lifetime deal customers are never deactivated by subscription events.
    if is_lifetime(lic):
        return HandlerResult(
            ok=True, action="noop",
            license_key=lic.key, message="lifetime license preserved",
        )
    lic.active = False
    lic.metadata["ls_status"] = attributes.get("status", "cancelled")
    await store.save(lic)
    return HandlerResult(
        ok=True, action="deactivated", license_key=lic.key,
        message=f"license deactivated for {email}",
    )


async def _on_payment_success(
    *, store: LicenseStore, email: str, attributes: dict,
) -> HandlerResult:
    """Reset the rolling period counter on successful renewal."""
    lic = await store.find_by_email(email)
    if lic is None:
        return HandlerResult(ok=True, action="noop", message="no license to reset")
    lic.period_calls = 0
    lic.period_started_at = datetime.now(timezone.utc)
    lic.active = True
    await store.save(lic)
    return HandlerResult(
        ok=True, action="period_reset", license_key=lic.key,
        message="usage counter reset on renewal",
    )


async def _on_payment_failed(
    *, store: LicenseStore, email: str, attributes: dict,
) -> HandlerResult:
    """Lemon Squeezy will retry; we keep the license active during grace."""
    lic = await store.find_by_email(email)
    if lic is None:
        return HandlerResult(ok=True, action="noop")
    lic.metadata["ls_last_payment_failed_at"] = datetime.now(timezone.utc).isoformat()
    await store.save(lic)
    return HandlerResult(
        ok=True, action="payment_failed_logged", license_key=lic.key,
        message="payment failure logged; license still active during grace period",
    )


async def _on_order_created(
    *, store: LicenseStore, email: str, variant_id: Optional[str],
    attributes: dict, entity_id: str,
    self_description: Optional[str] = None,
) -> HandlerResult:
    """Handle one-time orders (used for the lifetime deal)."""
    if not email:
        return HandlerResult(ok=False, action="error", message="missing email")
    lifetime_variant = _read_lifetime_variant()
    if not lifetime_variant or variant_id != lifetime_variant:
        return HandlerResult(
            ok=True, action="ignored",
            message=f"order_created for variant={variant_id!r} is not the lifetime SKU",
        )

    existing = await store.find_by_email(email)
    if existing is not None and is_lifetime(existing):
        return HandlerResult(
            ok=True, action="duplicate_lifetime",
            license_key=existing.key, message="email already has lifetime license",
        )

    # Auto-assign next deal_seq based on current count of lifetime licenses.
    deal_seq = await store.next_lifetime_seq()
    metadata: dict = {
        "lifetime": True,
        "deal_seq": deal_seq,
        "ls_order_id": entity_id,
        "ls_variant_id": variant_id,
        "issued_via": "order_created",
    }
    if self_description:
        metadata["self_description"] = self_description

    lic = License(
        key=issue_license_key(),
        plan=LIFETIME_DEAL_PLAN,
        customer_email=email,
        active=True,
        metadata=metadata,
    )
    await store.save(lic)
    return HandlerResult(
        ok=True, action="lifetime_issued", license_key=lic.key,
        message=f"lifetime deal #{deal_seq} issued to {email}",
    )
