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

    def test_origins_in_allowed_set(self):
        allowed = {"kr", "us", "uk", "eu", "other"}
        for r in ALL_INVESTORS:
            assert r.origin in allowed, f"{r.canonical} has unknown origin {r.origin}"
