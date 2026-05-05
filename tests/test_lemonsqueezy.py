from __future__ import annotations

import hashlib
import hmac
import json

import pytest

import koreanpulse.billing.lemonsqueezy as ls
from koreanpulse.billing.lemonsqueezy import (
    handle_event,
    verify_signature,
)
from koreanpulse.license import (
    InMemoryLicenseStore,
    Plan,
    is_lifetime,
)


SECRET = "test-webhook-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _reset_seen():
    ls._seen._set.clear()
    ls._seen._order.clear()
    yield
    ls._seen._set.clear()
    ls._seen._order.clear()


@pytest.fixture
def variant_env(monkeypatch):
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_STARTER", "1001")
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_INDIE", "1002")
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_PRO", "1003")
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_ENTERPRISE", "1004")
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_LIFETIME", "9999")


def make_payload(event_name: str, **attrs) -> dict:
    return {
        "meta": {
            "event_name": event_name,
            "test_mode": True,
            "webhook_id": f"wh_{event_name}_{attrs.get('id', '1')}",
        },
        "data": {
            "type": "subscriptions" if event_name.startswith("subscription") else "orders",
            "id": str(attrs.get("id", "1")),
            "attributes": attrs,
        },
    }


class TestVerifySignature:
    def test_valid_signature(self):
        body = b'{"hello":"world"}'
        sig = sign(body)
        assert verify_signature(body=body, signature_header=sig, secret=SECRET)

    def test_invalid_signature(self):
        body = b'{"hello":"world"}'
        assert not verify_signature(
            body=body, signature_header="deadbeef" * 8, secret=SECRET
        )

    def test_missing_signature(self):
        body = b'{}'
        assert not verify_signature(body=body, signature_header="", secret=SECRET)

    def test_missing_secret(self):
        body = b'{}'
        assert not verify_signature(body=body, signature_header=sign(body), secret="")

    def test_tampered_body_fails(self):
        body = b'{"price":100}'
        sig = sign(body)
        assert not verify_signature(
            body=b'{"price":1000000}', signature_header=sig, secret=SECRET
        )


class TestSubscriptionCreated:
    @pytest.mark.asyncio
    async def test_issues_new_license(self, variant_env):
        store = InMemoryLicenseStore()
        payload = make_payload(
            "subscription_created",
            id=42, user_email="alice@example.com", variant_id=1002,
            status="active", variant_name="Indie",
        )
        result = await handle_event(payload, store=store)

        assert result.ok
        assert result.action == "issued"
        assert result.license_key is not None

        lic = await store.get(result.license_key)
        assert lic is not None
        assert lic.plan == Plan.INDIE
        assert lic.customer_email == "alice@example.com"
        assert lic.active

    @pytest.mark.asyncio
    async def test_unknown_variant_errors(self, variant_env):
        store = InMemoryLicenseStore()
        payload = make_payload(
            "subscription_created",
            id=42, user_email="alice@example.com", variant_id=99999,
        )
        result = await handle_event(payload, store=store)
        assert not result.ok
        assert "unknown variant" in result.message

    @pytest.mark.asyncio
    async def test_existing_email_upgrades_in_place(self, variant_env):
        store = InMemoryLicenseStore()
        # First create at Starter
        await handle_event(
            make_payload(
                "subscription_created",
                id=1, user_email="alice@example.com", variant_id=1001,
            ),
            store=store,
        )
        # Then upgrade to Pro
        result = await handle_event(
            make_payload(
                "subscription_created",
                id=2, user_email="alice@example.com", variant_id=1003,
            ),
            store=store,
        )
        assert result.action == "upgraded"
        lic = await store.get(result.license_key)
        assert lic.plan == Plan.PRO


class TestSubscriptionLifecycle:
    @pytest.mark.asyncio
    async def test_cancelled_deactivates(self, variant_env):
        store = InMemoryLicenseStore()
        created = await handle_event(
            make_payload(
                "subscription_created",
                id=1, user_email="bob@example.com", variant_id=1002,
            ),
            store=store,
        )
        result = await handle_event(
            make_payload(
                "subscription_cancelled",
                id=1, user_email="bob@example.com", status="cancelled",
            ),
            store=store,
        )
        assert result.action == "deactivated"
        lic = await store.get(created.license_key)
        assert lic.active is False

    @pytest.mark.asyncio
    async def test_payment_success_resets_period(self, variant_env):
        store = InMemoryLicenseStore()
        created = await handle_event(
            make_payload(
                "subscription_created",
                id=1, user_email="cara@example.com", variant_id=1002,
            ),
            store=store,
        )
        # Bump usage
        lic = await store.get(created.license_key)
        lic.period_calls = 4_500
        await store.save(lic)

        result = await handle_event(
            make_payload(
                "subscription_payment_success",
                id=1, user_email="cara@example.com",
            ),
            store=store,
        )
        assert result.action == "period_reset"
        lic = await store.get(created.license_key)
        assert lic.period_calls == 0

    @pytest.mark.asyncio
    async def test_subscription_updated_changes_plan(self, variant_env):
        store = InMemoryLicenseStore()
        created = await handle_event(
            make_payload(
                "subscription_created",
                id=1, user_email="dan@example.com", variant_id=1002,
            ),
            store=store,
        )
        result = await handle_event(
            make_payload(
                "subscription_updated",
                id=1, user_email="dan@example.com", variant_id=1003,
                status="active",
            ),
            store=store,
        )
        assert result.action == "updated"
        lic = await store.get(created.license_key)
        assert lic.plan == Plan.PRO


class TestLifetimeOrder:
    @pytest.mark.asyncio
    async def test_lifetime_order_issues_license(self, variant_env):
        store = InMemoryLicenseStore()
        payload = {
            "meta": {"event_name": "order_created", "webhook_id": "wh_o1"},
            "data": {
                "type": "orders",
                "id": "o1",
                "attributes": {
                    "id": "o1",
                    "user_email": "early@adopter.com",
                    "first_order_item": {"variant_id": 9999},
                },
            },
        }
        result = await handle_event(payload, store=store)
        assert result.ok
        assert result.action == "lifetime_issued"

        lic = await store.get(result.license_key)
        assert lic is not None
        assert lic.plan == Plan.ANALYST  # pricing v2: design-partner lifetime → Analyst forever
        assert is_lifetime(lic)
        assert lic.metadata["deal_seq"] == 1

    @pytest.mark.asyncio
    async def test_lifetime_order_increments_seq(self, variant_env):
        store = InMemoryLicenseStore()
        for i, email in enumerate(["a@x.com", "b@x.com", "c@x.com"], start=1):
            payload = {
                "meta": {"event_name": "order_created", "webhook_id": f"wh_o{i}"},
                "data": {
                    "type": "orders",
                    "id": f"o{i}",
                    "attributes": {
                        "id": f"o{i}",
                        "user_email": email,
                        "first_order_item": {"variant_id": 9999},
                    },
                },
            }
            r = await handle_event(payload, store=store)
            lic = await store.get(r.license_key)
            assert lic.metadata["deal_seq"] == i

    @pytest.mark.asyncio
    async def test_non_lifetime_order_ignored(self, variant_env):
        store = InMemoryLicenseStore()
        payload = {
            "meta": {"event_name": "order_created", "webhook_id": "wh_other"},
            "data": {
                "type": "orders",
                "id": "o1",
                "attributes": {
                    "user_email": "x@y.com",
                    "first_order_item": {"variant_id": 1001},  # Starter, not lifetime
                },
            },
        }
        result = await handle_event(payload, store=store)
        assert result.action == "ignored"

    @pytest.mark.asyncio
    async def test_subscription_cancel_does_not_revoke_lifetime(self, variant_env):
        store = InMemoryLicenseStore()
        # Issue lifetime first
        order = {
            "meta": {"event_name": "order_created", "webhook_id": "wh_o1"},
            "data": {
                "type": "orders",
                "id": "o1",
                "attributes": {
                    "user_email": "z@x.com",
                    "first_order_item": {"variant_id": 9999},
                },
            },
        }
        r = await handle_event(order, store=store)
        # Then a cancel for the same email
        cancel = make_payload(
            "subscription_cancelled", id=1, user_email="z@x.com",
        )
        cancel_result = await handle_event(cancel, store=store)
        assert cancel_result.action == "noop"
        lic = await store.get(r.license_key)
        assert lic.active is True  # lifetime preserved


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_duplicate_webhook_ignored(self, variant_env):
        store = InMemoryLicenseStore()
        payload = make_payload(
            "subscription_created",
            id=99, user_email="dup@example.com", variant_id=1002,
        )
        first = await handle_event(payload, store=store)
        second = await handle_event(payload, store=store)

        assert first.action == "issued"
        assert second.action == "duplicate_ignored"


class TestUnknownEvents:
    @pytest.mark.asyncio
    async def test_unknown_event_returns_ok_ignored(self, variant_env):
        store = InMemoryLicenseStore()
        payload = {
            "meta": {"event_name": "license_key_created", "webhook_id": "wh_lk1"},
            "data": {"attributes": {"user_email": "x@y.com"}},
        }
        result = await handle_event(payload, store=store)
        assert result.ok
        assert result.action == "ignored"


class TestSelfDescriptionCapture:
    """Audience composition signal — captured at LS checkout via custom field."""

    @pytest.mark.asyncio
    async def test_role_from_meta_custom_data(self, variant_env):
        store = InMemoryLicenseStore()
        payload = {
            "meta": {
                "event_name": "subscription_created",
                "webhook_id": "wh_role_1",
                "custom_data": {"role": "rotator"},
            },
            "data": {
                "type": "subscriptions",
                "id": "1",
                "attributes": {
                    "user_email": "jay@example.com",
                    "variant_id": 1002,
                    "status": "active",
                },
            },
        }
        result = await handle_event(payload, store=store)
        assert result.ok
        lic = await store.get(result.license_key)
        assert lic.metadata["self_description"] == "rotator"

    @pytest.mark.asyncio
    async def test_role_from_product_options(self, variant_env):
        store = InMemoryLicenseStore()
        payload = {
            "meta": {"event_name": "order_created", "webhook_id": "wh_role_2"},
            "data": {
                "type": "orders",
                "id": "o1",
                "attributes": {
                    "user_email": "alice@example.com",
                    "first_order_item": {
                        "variant_id": 9999,
                        "product_options": {"custom": {"role": "analyst"}},
                    },
                },
            },
        }
        result = await handle_event(payload, store=store)
        assert result.ok
        assert result.action == "lifetime_issued"
        lic = await store.get(result.license_key)
        assert lic.metadata["self_description"] == "analyst"

    @pytest.mark.asyncio
    async def test_unknown_role_normalises_to_other(self, variant_env):
        store = InMemoryLicenseStore()
        payload = {
            "meta": {
                "event_name": "subscription_created",
                "webhook_id": "wh_role_3",
                "custom_data": {"role": "🤷 some weird value"},
            },
            "data": {
                "type": "subscriptions",
                "id": "2",
                "attributes": {
                    "user_email": "weird@example.com",
                    "variant_id": 1002,
                    "status": "active",
                },
            },
        }
        result = await handle_event(payload, store=store)
        lic = await store.get(result.license_key)
        assert lic.metadata["self_description"] == "other"

    @pytest.mark.asyncio
    async def test_missing_role_no_field(self, variant_env):
        """No role in payload → metadata key absent, not blank."""
        store = InMemoryLicenseStore()
        payload = make_payload(
            "subscription_created",
            id=3, user_email="silent@example.com", variant_id=1002,
        )
        result = await handle_event(payload, store=store)
        lic = await store.get(result.license_key)
        assert "self_description" not in lic.metadata

    @pytest.mark.asyncio
    async def test_role_preserved_on_upgrade(self, variant_env):
        """Subscription update without role must NOT clear an earlier role."""
        store = InMemoryLicenseStore()
        # First create at Starter with role
        await handle_event(
            {
                "meta": {
                    "event_name": "subscription_created",
                    "webhook_id": "wh_role_4a",
                    "custom_data": {"role": "developer"},
                },
                "data": {
                    "type": "subscriptions",
                    "id": "10",
                    "attributes": {
                        "user_email": "dev@example.com",
                        "variant_id": 1001,
                        "status": "active",
                    },
                },
            },
            store=store,
        )
        # Then upgrade to Pro without a role payload
        result = await handle_event(
            make_payload(
                "subscription_created",
                id=11, user_email="dev@example.com", variant_id=1003,
            ),
            store=store,
        )
        assert result.action == "upgraded"
        lic = await store.get(result.license_key)
        assert lic.metadata["self_description"] == "developer"
