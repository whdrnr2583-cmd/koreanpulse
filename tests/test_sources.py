"""Tests for the news-source registry — added 2026-07-08 alongside the
koreaherald/zdnet additions. Guards the `language` field default and keeps
a regression check that the three explicitly-rejected candidates (asiae,
sedaily, yonhap — RSS-specific commercial/AI-training restrictions, see
sources.py module docstring) never silently reappear.
"""
from __future__ import annotations

from koreanpulse.sources import NEWS_SOURCE_BY_KEY, NEWS_SOURCES


class TestNewsSourceRegistry:
    def test_koreaherald_present_and_english(self):
        src = NEWS_SOURCE_BY_KEY["koreaherald"]
        assert src.language == "en"
        assert src.rss_url is not None
        assert src.rss_url.startswith("https://")

    def test_zdnet_present_and_korean(self):
        src = NEWS_SOURCE_BY_KEY["zdnet"]
        assert src.language == "ko"
        assert src.rss_url is not None
        assert src.rss_url.startswith("https://")

    def test_existing_sources_default_to_korean(self):
        for key in ("etnews", "hankyung"):
            assert NEWS_SOURCE_BY_KEY[key].language == "ko"

    def test_no_rss_sources_still_have_none_url(self):
        # MK / ChosunBiz — deliberately not scraped (see sources.py docstring).
        for key in ("mk", "chosunbiz"):
            assert NEWS_SOURCE_BY_KEY[key].rss_url is None

    def test_rejected_candidates_are_not_present(self):
        """asiae / sedaily / yonhap were evaluated 2026-07-08 and rejected
        for explicit RSS-specific commercial/AI-training restrictions —
        must not silently reappear as a source key."""
        rejected_keys = {"asiae", "sedaily", "yonhap", "yna"}
        assert rejected_keys.isdisjoint(NEWS_SOURCE_BY_KEY.keys())

    def test_every_source_has_attribution(self):
        for src in NEWS_SOURCES:
            assert src.attribution.strip()

    def test_source_keys_are_unique(self):
        keys = [s.key for s in NEWS_SOURCES]
        assert len(keys) == len(set(keys))
