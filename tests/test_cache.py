from __future__ import annotations

import time

import pytest

from koreanpulse.cache import FileCache, NullCache, cache_key


class TestCacheKey:
    def test_deterministic(self):
        a = cache_key("translate", "ko", "en", "삼성전자")
        b = cache_key("translate", "ko", "en", "삼성전자")
        assert a == b

    def test_different_inputs_diverge(self):
        a = cache_key("translate", "ko", "en", "삼성전자")
        b = cache_key("translate", "ko", "en", "현대차")
        assert a != b

    def test_namespace_prefix(self):
        k = cache_key("translate", "x")
        assert k.startswith("translate:")


class TestNullCache:
    @pytest.mark.asyncio
    async def test_always_miss(self):
        c = NullCache()
        await c.set("k", "v")
        assert await c.get("k") is None

    @pytest.mark.asyncio
    async def test_ttl_arg_accepted(self):
        c = NullCache()
        await c.set("k", "v", ttl_seconds=60)
        assert await c.get("k") is None


class TestFileCache:
    @pytest.mark.asyncio
    async def test_set_get_roundtrip(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("translate:abc", "Hello")
        assert await c.get("translate:abc") == "Hello"

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path):
        root = tmp_path / "cache"
        c1 = FileCache(root=root)
        await c1.set("translate:abc", "Hello")

        # New instance, same root → should load from disk
        c2 = FileCache(root=root)
        assert await c2.get("translate:abc") == "Hello"

    @pytest.mark.asyncio
    async def test_namespace_isolation(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("translate:abc", "Hello")
        await c.set("summarize:abc", "Summary")
        assert await c.get("translate:abc") == "Hello"
        assert await c.get("summarize:abc") == "Summary"

    @pytest.mark.asyncio
    async def test_unicode(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("translate:k", "안녕하세요")
        assert await c.get("translate:k") == "안녕하세요"


class TestFileCacheTTL:
    @pytest.mark.asyncio
    async def test_no_ttl_never_expires(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("translate:perm", "forever")
        # Even after the future, no TTL means stays
        assert await c.get("translate:perm") == "forever"

    @pytest.mark.asyncio
    async def test_ttl_in_future_returns_value(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("dart_list:k", "fresh", ttl_seconds=60)
        assert await c.get("dart_list:k") == "fresh"

    @pytest.mark.asyncio
    async def test_ttl_zero_returns_none(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("dart_list:k", "ephemeral", ttl_seconds=0)
        # Sleep tiny amount so wall clock advances past exp
        time.sleep(0.01)
        assert await c.get("dart_list:k") is None

    @pytest.mark.asyncio
    async def test_ttl_negative_returns_none(self, tmp_path):
        # Manually craft expired entry — simulate writing then waiting
        c = FileCache(root=tmp_path / "cache")
        await c.set("dart_list:k", "stale", ttl_seconds=1)
        # Force-expire by manipulating in-memory entry
        c._stores["dart_list"]["dart_list:k"]["exp"] = time.time() - 100
        assert await c.get("dart_list:k") is None

    @pytest.mark.asyncio
    async def test_ttl_persistence_survives_reload(self, tmp_path):
        root = tmp_path / "cache"
        c1 = FileCache(root=root)
        await c1.set("dart_list:k", "fresh", ttl_seconds=3600)

        c2 = FileCache(root=root)
        # New instance, ttl info preserved on disk
        assert await c2.get("dart_list:k") == "fresh"

    @pytest.mark.asyncio
    async def test_ttl_overwrites_previous_entry(self, tmp_path):
        c = FileCache(root=tmp_path / "cache")
        await c.set("dart_list:k", "old", ttl_seconds=3600)
        await c.set("dart_list:k", "new", ttl_seconds=7200)
        assert await c.get("dart_list:k") == "new"
