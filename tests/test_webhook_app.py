from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import koreanpulse.billing.lemonsqueezy as ls
from koreanpulse.billing.webhook_app import _build_app
from koreanpulse.license import (
    InMemoryLicenseStore,
    License,
    Plan,
    issue_license_key,
    set_default_store,
)


SECRET = "integration-test-secret"
CACHE_SECRET = "integration-test-cache-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def _reset_seen():
    ls._seen._set.clear()
    ls._seen._order.clear()
    yield


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_INDIE", "1002")
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_LIFETIME", "9999")
    monkeypatch.setenv("KOREANPULSE_CACHE_SHARED_SECRET", CACHE_SECRET)

    # Fresh in-memory store, isolated per test
    store = InMemoryLicenseStore()
    set_default_store(store)

    app = _build_app()
    return TestClient(app), store


class TestHealthRoute:
    def test_health(self, app_client):
        client, _ = app_client
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestWebhookRoute:
    def test_missing_signature_rejected(self, app_client):
        client, _ = app_client
        body = b"{}"
        r = client.post("/webhook/lemonsqueezy", content=body)
        assert r.status_code == 401

    def test_bad_signature_rejected(self, app_client):
        client, _ = app_client
        body = b"{}"
        r = client.post(
            "/webhook/lemonsqueezy",
            content=body,
            headers={"X-Signature": "deadbeef" * 8},
        )
        assert r.status_code == 401

    def test_invalid_json_rejected(self, app_client):
        client, _ = app_client
        body = b"not json"
        r = client.post(
            "/webhook/lemonsqueezy",
            content=body,
            headers={"X-Signature": sign(body)},
        )
        assert r.status_code == 400

    def test_subscription_created_end_to_end(self, app_client):
        client, store = app_client
        payload = {
            "meta": {"event_name": "subscription_created", "webhook_id": "wh_e2e_1"},
            "data": {
                "type": "subscriptions",
                "id": "1",
                "attributes": {
                    "id": "1",
                    "user_email": "endtoend@example.com",
                    "variant_id": 1002,
                    "status": "active",
                },
            },
        }
        body = json.dumps(payload).encode("utf-8")
        r = client.post(
            "/webhook/lemonsqueezy",
            content=body,
            headers={"X-Signature": sign(body)},
        )
        assert r.status_code == 200
        result = r.json()
        assert result["ok"]
        assert result["action"] == "issued"
        assert result["license_key"]

        # License really got into the shared store
        # (use sync wrapper since TestClient already drove async)
        import asyncio
        lic = asyncio.run(store.get(result["license_key"]))
        assert lic is not None
        assert lic.customer_email == "endtoend@example.com"

    def test_unconfigured_secret_returns_500(self, monkeypatch):
        monkeypatch.delenv("LEMONSQUEEZY_WEBHOOK_SECRET", raising=False)
        app = _build_app()
        client = TestClient(app)
        body = b"{}"
        r = client.post(
            "/webhook/lemonsqueezy",
            content=body,
            headers={"X-Signature": sign(body)},
        )
        assert r.status_code == 500


class TestValidateRoute:
    """The /v1/validate endpoint that the koreanpulse-cache Worker calls."""

    def _post_validate(self, client, payload: dict, secret: str = CACHE_SECRET):
        body = json.dumps(payload).encode("utf-8")
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return client.post(
            "/v1/validate",
            content=body,
            headers={"X-Cache-Signature": sig},
        )

    def test_valid_active_license(self, app_client):
        client, store = app_client
        # Seed a license directly in the store
        import asyncio
        lic = License(
            key=issue_license_key(),
            plan=Plan.INDIE,
            customer_email="paid@example.com",
        )
        asyncio.run(store.save(lic))

        r = self._post_validate(client, {"license_key": lic.key})
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] is True
        assert result["plan"] == "indie"
        assert result["period_calls"] == 1  # validate charges 1 unit

    def test_unknown_license_returns_invalid(self, app_client):
        client, _ = app_client
        r = self._post_validate(client, {"license_key": "kp_does_not_exist"})
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] is False
        assert result["code"] == "invalid"

    def test_missing_license_key(self, app_client):
        client, _ = app_client
        r = self._post_validate(client, {})
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] is False
        assert result["code"] == "missing"

    def test_bad_signature_rejected(self, app_client):
        client, _ = app_client
        body = json.dumps({"license_key": "kp_anything"}).encode("utf-8")
        r = client.post(
            "/v1/validate",
            content=body,
            headers={"X-Cache-Signature": "deadbeef" * 8},
        )
        assert r.status_code == 401

    def test_missing_signature_rejected(self, app_client):
        client, _ = app_client
        body = json.dumps({"license_key": "kp_anything"}).encode("utf-8")
        r = client.post("/v1/validate", content=body)
        assert r.status_code == 401

    def test_unconfigured_cache_secret_returns_500(self, monkeypatch):
        # Build a fresh app *without* the cache secret env
        monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", SECRET)
        monkeypatch.delenv("KOREANPULSE_CACHE_SHARED_SECRET", raising=False)
        app = _build_app()
        client = TestClient(app)
        body = b'{"license_key":"kp_x"}'
        sig = hmac.new(b"any", body, hashlib.sha256).hexdigest()
        r = client.post(
            "/v1/validate",
            content=body,
            headers={"X-Cache-Signature": sig},
        )
        assert r.status_code == 500

    def test_inactive_license(self, app_client):
        client, store = app_client
        import asyncio
        lic = License(
            key=issue_license_key(),
            plan=Plan.STARTER,
            customer_email="cancelled@example.com",
            active=False,
        )
        asyncio.run(store.save(lic))

        r = self._post_validate(client, {"license_key": lic.key})
        assert r.status_code == 200
        result = r.json()
        assert result["ok"] is False
        assert result["code"] == "inactive"
