from __future__ import annotations

import pytest

from koreanpulse.license import (
    InMemoryLicenseStore,
    LIFETIME_DEAL_MAX_SEATS,
    LIFETIME_DEAL_PRICE_USD,
    License,
    LicenseError,
    PLAN_LIMITS,
    PLAN_PRICING_USD,
    Plan,
    is_lifetime,
    issue_license_key,
    issue_lifetime_license,
    validate_license_or_raise,
)


def make_license(plan: Plan = Plan.SOLO) -> License:
    return License(key=issue_license_key(), plan=plan, customer_email="t@example.com")


class TestPlanCatalog:
    def test_all_plans_have_pricing(self):
        for plan in Plan:
            assert plan in PLAN_PRICING_USD
            assert PLAN_PRICING_USD[plan] >= 0

    def test_all_plans_have_limits(self):
        for plan in Plan:
            assert plan in PLAN_LIMITS
            limits = PLAN_LIMITS[plan]
            assert "calls_per_month" in limits
            assert "watchlists" in limits
            assert "retention_days" in limits

    def test_active_pricing_v2_ladder(self):
        # Pricing v2 (2026-05-05): Cloud Solo $29 / Analyst $79 / Desk $249.
        # Workflow-priced tier ladder; monotonic by design.
        assert PLAN_PRICING_USD[Plan.SOLO] == 29
        assert PLAN_PRICING_USD[Plan.ANALYST] == 79
        assert PLAN_PRICING_USD[Plan.DESK] == 249
        # Strictly increasing.
        assert (
            PLAN_PRICING_USD[Plan.SOLO]
            < PLAN_PRICING_USD[Plan.ANALYST]
            < PLAN_PRICING_USD[Plan.DESK]
        )

    def test_deprecated_plans_alias_solo_price(self):
        # FREE / STARTER / INDIE / PRO / ENTERPRISE are deprecated. Historical
        # rows resolve to Solo limits; pricing aliases Solo so analytics
        # don't break.
        assert PLAN_PRICING_USD[Plan.FREE] == 0  # FREE stays $0 (web-only)
        for deprecated in (Plan.STARTER, Plan.INDIE, Plan.PRO, Plan.ENTERPRISE):
            assert PLAN_PRICING_USD[deprecated] == PLAN_PRICING_USD[Plan.SOLO]

    def test_active_tier_limits_strictly_increasing(self):
        # Solo < Analyst < Desk on the metered fields.
        for field in ("calls_per_month", "watchlists", "alert_channels"):
            assert (
                PLAN_LIMITS[Plan.SOLO][field]
                < PLAN_LIMITS[Plan.ANALYST][field]
                < PLAN_LIMITS[Plan.DESK][field]
            )

    def test_desk_has_3_seats(self):
        assert PLAN_LIMITS[Plan.DESK]["seats"] == 3
        assert PLAN_LIMITS[Plan.SOLO]["seats"] == 1
        assert PLAN_LIMITS[Plan.ANALYST]["seats"] == 1


class TestKeyGeneration:
    def test_unique(self):
        keys = {issue_license_key() for _ in range(100)}
        assert len(keys) == 100

    def test_prefix(self):
        assert issue_license_key().startswith("kp_")


class TestValidate:
    @pytest.mark.asyncio
    async def test_missing_key_raises(self):
        with pytest.raises(LicenseError) as exc_info:
            await validate_license_or_raise(None, store=InMemoryLicenseStore())
        assert exc_info.value.code == "missing"

    @pytest.mark.asyncio
    async def test_invalid_key_raises(self):
        store = InMemoryLicenseStore()
        with pytest.raises(LicenseError) as exc_info:
            await validate_license_or_raise("kp_doesnotexist", store=store)
        assert exc_info.value.code == "invalid"

    @pytest.mark.asyncio
    async def test_inactive_key_raises(self):
        store = InMemoryLicenseStore()
        lic = make_license()
        lic.active = False
        await store.save(lic)
        with pytest.raises(LicenseError) as exc_info:
            await validate_license_or_raise(lic.key, store=store)
        assert exc_info.value.code == "inactive"

    @pytest.mark.asyncio
    async def test_solo_quota_exceeded(self):
        store = InMemoryLicenseStore()
        lic = make_license(Plan.SOLO)
        lic.period_calls = PLAN_LIMITS[Plan.SOLO]["calls_per_month"]
        await store.save(lic)
        with pytest.raises(LicenseError) as exc_info:
            await validate_license_or_raise(lic.key, store=store, cost_units=1)
        assert exc_info.value.code == "quota_exceeded"

    @pytest.mark.asyncio
    async def test_normal_call_increments(self):
        store = InMemoryLicenseStore()
        lic = make_license(Plan.ANALYST)
        await store.save(lic)
        result = await validate_license_or_raise(lic.key, store=store, cost_units=2)
        assert result.plan == Plan.ANALYST
        post = await store.get(lic.key)
        assert post.period_calls == 2

    @pytest.mark.asyncio
    async def test_analyst_tier_quota_boundary(self):
        store = InMemoryLicenseStore()
        lic = make_license(Plan.ANALYST)
        lic.period_calls = PLAN_LIMITS[Plan.ANALYST]["calls_per_month"] - 1
        await store.save(lic)
        await validate_license_or_raise(lic.key, store=store, cost_units=1)
        with pytest.raises(LicenseError) as exc_info:
            await validate_license_or_raise(lic.key, store=store, cost_units=1)
        assert exc_info.value.code == "quota_exceeded"

    @pytest.mark.asyncio
    async def test_desk_higher_quota_than_analyst(self):
        # Desk should accept usage that would exceed Analyst's cap.
        store = InMemoryLicenseStore()
        lic = make_license(Plan.DESK)
        lic.period_calls = PLAN_LIMITS[Plan.ANALYST]["calls_per_month"] + 1
        await store.save(lic)
        # Should pass — Desk has 100K, Analyst 15K.
        await validate_license_or_raise(lic.key, store=store, cost_units=1)


class TestLifetimeDeal:
    def test_issue_lifetime_license(self):
        # Pricing v2: Design Partner Lifetime $299, 20 seats, grants Analyst.
        lic = issue_lifetime_license(customer_email="early@adopter.com", deal_seq=1)
        assert lic.plan == Plan.ANALYST
        assert is_lifetime(lic)
        assert lic.metadata["deal_seq"] == 1
        assert lic.metadata["deal_price_usd"] == LIFETIME_DEAL_PRICE_USD
        assert LIFETIME_DEAL_PRICE_USD == 299
        assert LIFETIME_DEAL_MAX_SEATS == 20

    def test_lifetime_deal_seq_bounds(self):
        with pytest.raises(ValueError):
            issue_lifetime_license(customer_email="x@y.com", deal_seq=0)
        with pytest.raises(ValueError):
            issue_lifetime_license(
                customer_email="x@y.com", deal_seq=LIFETIME_DEAL_MAX_SEATS + 1
            )

    def test_is_lifetime_false_for_normal_license(self):
        lic = make_license()
        assert not is_lifetime(lic)

    @pytest.mark.asyncio
    async def test_lifetime_license_validates_normally(self):
        store = InMemoryLicenseStore()
        lic = issue_lifetime_license(customer_email="x@y.com", deal_seq=15)
        await store.save(lic)
        result = await validate_license_or_raise(lic.key, store=store)
        assert result.key == lic.key
        assert is_lifetime(result)
