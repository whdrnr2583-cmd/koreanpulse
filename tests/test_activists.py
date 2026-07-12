from __future__ import annotations

from koreanpulse.activists import (
    ALL_INVESTORS,
    FOREIGN_HOLDERS,
    KOREAN_ACTIVISTS,
    InvestorClass,
    match_activist,
    match_foreign_holder,
    match_investor,
)


class TestMatchActivist:
    """Backwards-compat — `match_activist` returns activist canonical only."""

    def test_kcgi_korean(self):
        assert match_activist("KCGI 제일호 사모투자합자회사") == "KCGI"

    def test_kcgi_strong_brand(self):
        assert match_activist("강성부펀드") == "KCGI"

    def test_align_partners_korean(self):
        assert match_activist("얼라인파트너스자산운용") == "Align Partners"

    def test_align_partners_english(self):
        assert match_activist("Align Partners Capital Management") == "Align Partners"

    def test_truston(self):
        assert match_activist("트러스톤자산운용") == "Truston Asset"

    def test_no_match(self):
        assert match_activist("국민연금공단") is None

    def test_empty(self):
        assert match_activist(None) is None
        assert match_activist("") is None
        assert match_activist("   ") is None

    def test_case_insensitive_english(self):
        assert match_activist("VALUEACT CAPITAL") == "ValueAct Capital"
        assert match_activist("elliott management") == "Elliott Management"

    def test_mixed_korean_english(self):
        assert match_activist("KCGI 자산운용") == "KCGI"

    def test_foreign_holder_returns_none_from_activist_matcher(self):
        """`match_activist` must NOT return foreign-holder names."""
        assert match_activist("BlackRock Inc.") is None
        assert match_activist("뱅가드자산운용") is None
        assert match_activist("Norges Bank") is None


class TestMatchActivistNewEntries2026_07_08:
    """Activist allowlist refresh — verified via 2024-2026 Korean press
    (see activists.py per-entry comments for citations)."""

    def test_must_asset_management(self):
        assert match_activist("머스트자산운용") == "Must Asset Management"
        assert match_activist("Must Asset Management LLC") == "Must Asset Management"

    def test_dalton_investments(self):
        assert match_activist("달튼인베스트먼트코리아") == "Dalton Investments"
        assert match_activist("Dalton Investments LLC") == "Dalton Investments"

    def test_flashlight_capital_partners(self):
        assert match_activist("플래시라이트캐피탈파트너스") == "Flashlight Capital Partners"
        assert match_activist("Flashlight Capital Partners Pte Ltd") == "Flashlight Capital Partners"

    def test_oasis_management(self):
        assert match_activist("오아시스매니지먼트") == "Oasis Management"
        assert match_activist("Oasis Management Co Ltd") == "Oasis Management"

    def test_palliser_capital(self):
        assert match_activist("팰리서캐피탈") == "Palliser Capital"
        assert match_activist("Palliser Capital (UK) LLP") == "Palliser Capital"

    def test_whitebox_advisors(self):
        assert match_activist("Whitebox Advisors LLC") == "Whitebox Advisors"

    def test_city_of_london_investment_management(self):
        assert match_activist("시티오브런던") == "City of London Investment Management"
        assert match_activist("City of London Investment Management Ltd") == "City of London Investment Management"

    def test_new_entries_do_not_leak_into_foreign_matcher(self):
        assert match_foreign_holder("머스트자산운용") is None
        assert match_foreign_holder("Palliser Capital") is None


class TestMatchForeignHolder:
    def test_blackrock(self):
        m = match_foreign_holder("BlackRock Fund Advisors")
        assert m is not None
        assert m.canonical == "BlackRock"
        assert m.klass is InvestorClass.FOREIGN
        assert m.origin == "us"

    def test_blackrock_korean(self):
        m = match_foreign_holder("블랙록자산운용")
        assert m is not None
        assert m.canonical == "BlackRock"

    def test_norges_uk_eu_other(self):
        norges = match_foreign_holder("Norges Bank Investment Management")
        assert norges is not None
        assert norges.origin == "eu"

        gic = match_foreign_holder("GIC Private Limited")
        assert gic is not None
        assert gic.origin == "other"

        aberdeen = match_foreign_holder("abrdn plc")
        assert aberdeen is not None
        assert aberdeen.canonical == "Aberdeen"
        assert aberdeen.origin == "uk"

    def test_temasek(self):
        m = match_foreign_holder("테마섹홀딩스")
        assert m is not None
        assert m.canonical == "Temasek"

    def test_jpmorgan_variants(self):
        for name in ("JPMorgan Chase", "JP Morgan Securities", "JP모건"):
            m = match_foreign_holder(name)
            assert m is not None
            assert m.canonical == "JPMorgan"

    def test_activist_returns_none_from_foreign_matcher(self):
        """`match_foreign_holder` must NOT return activist names."""
        assert match_foreign_holder("KCGI") is None
        assert match_foreign_holder("얼라인파트너스") is None
        assert match_foreign_holder("Elliott Management") is None

    def test_no_match(self):
        assert match_foreign_holder("국민연금공단") is None
        assert match_foreign_holder("Some Random Hedge Fund LLC") is None


class TestMatchInvestor:
    """Combined matcher — returns full metadata for either class."""

    def test_activist_match(self):
        m = match_investor("KCGI")
        assert m is not None
        assert m.canonical == "KCGI"
        assert m.klass is InvestorClass.ACTIVIST
        assert m.origin == "kr"

    def test_foreign_match(self):
        m = match_investor("Vanguard Group Inc.")
        assert m is not None
        assert m.canonical == "Vanguard"
        assert m.klass is InvestorClass.FOREIGN
        assert m.origin == "us"

    def test_no_match(self):
        assert match_investor("국민연금공단") is None
        assert match_investor(None) is None
        assert match_investor("") is None


class TestRegistries:
    def test_no_duplicate_canonicals_across_lists(self):
        all_names = [r.canonical for r in ALL_INVESTORS]
        assert len(all_names) == len(set(all_names))

    def test_at_least_one_alias_each(self):
        for r in ALL_INVESTORS:
            assert r.aliases_ko or r.aliases_en, f"{r.canonical} has no aliases"

    def test_classes_partitioned_correctly(self):
        for r in KOREAN_ACTIVISTS:
            assert r.klass is InvestorClass.ACTIVIST
        for r in FOREIGN_HOLDERS:
            assert r.klass is InvestorClass.FOREIGN

    def test_foreign_holders_count_at_least_15(self):
        # We documented 20 in marketplace listings; allow some attrition
        # but at least 15 must remain.
        assert len(FOREIGN_HOLDERS) >= 15

    def test_korean_activists_count_at_least_15(self):
        # Refreshed 2026-07-08: 10 -> 17. Allow some attrition but at
        # least 15 must remain (regression guard for the 2026-07-08 batch).
        assert len(KOREAN_ACTIVISTS) >= 15

    def test_origins_in_allowed_set(self):
        allowed = {"kr", "us", "uk", "eu", "other"}
        for r in ALL_INVESTORS:
            assert r.origin in allowed, f"{r.canonical} has unknown origin {r.origin}"


class TestWhiteboxAdvisorsKoreanAliases:
    """2026-07-12 — Whitebox Advisors previously had zero Korean aliases
    (`aliases_ko=()`), so a Korean-language filer name could never match
    it even though it's a named campaign participant."""

    def test_korean_alias_matches(self):
        assert match_activist("화이트박스") == "Whitebox Advisors"

    def test_korean_alias_variant_matches(self):
        assert match_activist("화이트박스어드바이저스") == "Whitebox Advisors"


class TestAliasDenylistFalsePositives:
    """2026-07-12 accuracy fix — a few allowlist aliases are short enough
    to also appear inside an unrelated real-world entity's name. These
    must resolve to None, not a false activist/foreign-holder tag."""

    def test_daniel_wellington_watch_brand_is_not_wellington_management(self):
        assert match_investor("다니엘웰링턴코리아") is None
        assert match_activist("다니엘웰링턴코리아") is None
        assert match_foreign_holder("다니엘웰링턴코리아") is None

    def test_jeil_capital_group_is_not_capital_group(self):
        assert match_investor("제일캐피탈그룹") is None
        assert match_foreign_holder("제일캐피탈그룹") is None

    def test_shilla_millennium_is_not_millennium_management(self):
        assert match_investor("신라밀레니엄") is None

    def test_daedong_millennium_is_not_millennium_management(self):
        assert match_investor("대동밀레니엄") is None

    def test_millennium_holdings_is_not_millennium_management(self):
        assert match_investor("밀레니엄홀딩스") is None

    def test_genuine_wellington_management_still_matches(self):
        m = match_foreign_holder("Wellington Management Company LLP")
        assert m is not None
        assert m.canonical == "Wellington Management"

    def test_genuine_wellington_management_korean_still_matches(self):
        m = match_foreign_holder("웰링턴자산운용")
        assert m is not None
        assert m.canonical == "Wellington Management"

    def test_genuine_capital_group_still_matches(self):
        m = match_foreign_holder("Capital Group Companies")
        assert m is not None
        assert m.canonical == "Capital Group"

    def test_genuine_capital_group_korean_still_matches(self):
        m = match_foreign_holder("캐피털그룹자산운용")
        assert m is not None
        assert m.canonical == "Capital Group"

    def test_genuine_millennium_still_matches(self):
        m = match_foreign_holder("Millennium Management LLC")
        assert m is not None
        assert m.canonical == "Millennium"

    def test_vanguard_kcgi_align_unaffected_by_denylist(self):
        """Regression guard — the denylist must not collaterally block
        unrelated existing allowlist entries."""
        v = match_foreign_holder("Vanguard Group Inc.")
        assert v is not None and v.canonical == "Vanguard"
        assert match_activist("KCGI 제일호 사모투자합자회사") == "KCGI"
        assert match_activist("얼라인파트너스자산운용") == "Align Partners"
