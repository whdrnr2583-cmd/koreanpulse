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


class TestCompaction:
    @pytest.mark.asyncio
    async def test_dead_lines_are_dropped_on_next_load(self, tmp_path):
        import json
        import time

        path = tmp_path / "dart_list.jsonl"
        now = time.time()
        lines = []
        # 300 superseded/expired writes of one hot key + 1 live key.
        for i in range(300):
            lines.append(json.dumps({"k": "dart_list:hot", "v": [i], "exp": now - 10}))
        lines.append(json.dumps({"k": "dart_list:keep", "v": ["live"], "exp": now + 3600}))
        lines.append(json.dumps({"k": "dart_list:forever", "v": 1, "exp": None}))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        cache = FileCache(root=tmp_path)
        assert await cache.get("dart_list:keep") == ["live"]
        assert await cache.get("dart_list:hot") is None
        assert await cache.get("dart_list:forever") == 1
        remaining = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert len(remaining) == 2
        assert not list(tmp_path.glob("*.tmp"))

    @pytest.mark.asyncio
    async def test_small_files_are_left_alone(self, tmp_path):
        import json

        path = tmp_path / "translate.jsonl"
        path.write_text(json.dumps({"k": "translate:a", "v": "x", "exp": 1.0}) + "\n")
        cache = FileCache(root=tmp_path)
        assert await cache.get("translate:a") is None
        assert path.read_text().count("\n") == 1

    @pytest.mark.asyncio
    async def test_live_entries_survive_a_restart_after_compaction(self, tmp_path):
        import json
        import time

        path = tmp_path / "ns.jsonl"
        now = time.time()
        rows = [json.dumps({"k": f"ns:{i}", "v": i, "exp": now - 1}) for i in range(250)]
        rows.append(json.dumps({"k": "ns:alive", "v": "yes", "exp": None}))
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        FileCache(root=tmp_path)._ensure_loaded("ns")
        again = FileCache(root=tmp_path)
        assert await again.get("ns:alive") == "yes"


class TestRuntimeCompaction:
    @pytest.mark.asyncio
    async def test_hot_key_rewrites_do_not_grow_the_file_unboundedly(self, tmp_path):
        """A 60 s-TTL filing key refetched all day used to append forever
        until the next restart."""
        cache = FileCache(root=tmp_path)
        for i in range(2000):
            await cache.set("dart_list:hot", ["x" * 200, i], ttl_seconds=3600)
        lines = (tmp_path / "dart_list.jsonl").read_text(encoding="utf-8").count("\n")
        assert lines < 600
        assert (await cache.get("dart_list:hot"))[1] == 1999
        fresh = FileCache(root=tmp_path)
        assert (await fresh.get("dart_list:hot"))[1] == 1999

    @pytest.mark.asyncio
    async def test_distinct_live_keys_are_all_kept(self, tmp_path):
        cache = FileCache(root=tmp_path)
        for i in range(700):
            await cache.set(f"translate:{i}", f"v{i}")
        assert await cache.get("translate:0") == "v0"
        assert await cache.get("translate:699") == "v699"
