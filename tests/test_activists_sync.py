"""Regression guard for the TS <-> PY activist/foreign-holder allowlist
sync contract documented in both `daily-worker/src/activists.ts` and
`src/koreanpulse/activists.py`.

Commit b7d58f5 describes an actual drift incident: `85becb5` claimed
("kept in sync with src/koreanpulse/activists.py") while `8c6dcf7`'s
Python-side fixes (`_ALIAS_DENYLIST`, Whitebox Advisors' `aliases_ko`)
were never ported to the TS file — the daily-worker dashboard kept
mistagging Daniel Wellington / 제일캐피탈그룹 / 신라밀레니엄 etc. as real
fund matches, and never matched Korean-language Whitebox filings, until
that commit manually re-synced both sides.

At the time that fix landed, the only verification was a manual "37
records identical" check. This file makes that check automatic: it
parses the TS source (regex-based, no Node/tsc dependency) into the
same shape as the Python `InvestorRecord` tuples and diffs them field
by field, plus the `_ALIAS_DENYLIST` dict.
"""
from __future__ import annotations

import re
from pathlib import Path

from koreanpulse.activists import ALL_INVESTORS, _ALIAS_DENYLIST

TS_PATH = (
    Path(__file__).resolve().parent.parent / "daily-worker" / "src" / "activists.ts"
)

_TS_SOURCE = TS_PATH.read_text(encoding="utf-8")

# Matches one `{ canonical: "...", klass: "...", origin: "...",
# aliasesKo: [...], aliasesEn: [...] },` object-literal record. The TS
# source formats every record on a single line, so this is intentionally
# not a general TS/JS parser — just enough structure to extract the
# fields this file needs to compare.
_RECORD_RE = re.compile(
    r'canonical:\s*"(?P<canonical>[^"]+)"\s*,\s*'
    r'klass:\s*"(?P<klass>[^"]+)"\s*,\s*'
    r'origin:\s*"(?P<origin>[^"]+)"\s*,\s*'
    r'aliasesKo:\s*\[(?P<aliases_ko>[^\]]*)\]\s*,\s*'
    r'aliasesEn:\s*\[(?P<aliases_en>[^\]]*)\]'
)

_STRING_LIST_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _parse_string_list(raw: str) -> tuple[str, ...]:
    return tuple(m.group(1) for m in _STRING_LIST_RE.finditer(raw))


def _parse_ts_records() -> dict[str, dict]:
    records: dict[str, dict] = {}
    for m in _RECORD_RE.finditer(_TS_SOURCE):
        canonical = m.group("canonical")
        assert canonical not in records, f"duplicate canonical in TS source: {canonical}"
        records[canonical] = {
            "klass": m.group("klass"),
            "origin": m.group("origin"),
            "aliases_ko": _parse_string_list(m.group("aliases_ko")),
            "aliases_en": _parse_string_list(m.group("aliases_en")),
        }
    return records


# Matches the `ALIAS_DENYLIST` TS object — `Key: [...]` or `"Key": [...]`
# entries, one per line, inside the `Record<string, string[]> = { ... }`
# literal.
_DENYLIST_BLOCK_RE = re.compile(
    r"const ALIAS_DENYLIST: Record<string, string\[\]> = \{(?P<body>.*?)\n\};",
    re.DOTALL,
)
_DENYLIST_ENTRY_RE = re.compile(
    r'^\s*(?:"(?P<qkey>[^"]+)"|(?P<bkey>[A-Za-z_][A-Za-z0-9_]*))\s*:\s*\[(?P<vals>[^\]]*)\]',
    re.MULTILINE,
)


def _parse_ts_denylist() -> dict[str, tuple[str, ...]]:
    block_match = _DENYLIST_BLOCK_RE.search(_TS_SOURCE)
    assert block_match is not None, "ALIAS_DENYLIST block not found in activists.ts"
    body = block_match.group("body")
    out: dict[str, tuple[str, ...]] = {}
    for m in _DENYLIST_ENTRY_RE.finditer(body):
        key = m.group("qkey") or m.group("bkey")
        out[key] = _parse_string_list(m.group("vals"))
    return out


class TestTsSourceParses:
    """Sanity checks on the regex parser itself — if these fail, the
    comparison tests below can't be trusted (either the TS file's format
    changed in a way the parser doesn't handle, or the file is missing)."""

    def test_ts_file_exists(self):
        assert TS_PATH.is_file(), f"expected daily-worker source at {TS_PATH}"

    def test_parses_at_least_30_records(self):
        records = _parse_ts_records()
        assert len(records) >= 30, (
            f"TS parser only found {len(records)} records — likely a format "
            "drift in activists.ts that the regex parser needs updating for, "
            "not necessarily a real sync bug"
        )

    def test_parses_denylist_with_known_keys(self):
        denylist = _parse_ts_denylist()
        assert "Wellington Management" in denylist
        assert "Capital Group" in denylist
        assert "Millennium" in denylist


class TestRecordCountSync:
    def test_ts_and_py_have_same_record_count(self):
        ts_records = _parse_ts_records()
        assert len(ts_records) == len(ALL_INVESTORS), (
            f"TS activists.ts has {len(ts_records)} records but Python "
            f"activists.py has {len(ALL_INVESTORS)} — the two allowlists "
            "have drifted out of sync (see b7d58f5)"
        )

    def test_37_records_both_sides(self):
        """Pins the specific count b7d58f5 verified by hand ('37 records
        identical') so a silent future drift in *both* files together
        (unlikely, but possible) still trips a test."""
        ts_records = _parse_ts_records()
        assert len(ts_records) == 37
        assert len(ALL_INVESTORS) == 37


class TestRecordFieldsSync:
    def test_every_py_record_exists_in_ts_with_matching_fields(self):
        ts_records = _parse_ts_records()
        missing = []
        mismatched = []
        for rec in ALL_INVESTORS:
            ts_rec = ts_records.get(rec.canonical)
            if ts_rec is None:
                missing.append(rec.canonical)
                continue
            if ts_rec["klass"] != rec.klass.value:
                mismatched.append(
                    f"{rec.canonical}: klass py={rec.klass.value!r} ts={ts_rec['klass']!r}"
                )
            if ts_rec["origin"] != rec.origin:
                mismatched.append(
                    f"{rec.canonical}: origin py={rec.origin!r} ts={ts_rec['origin']!r}"
                )
            if set(ts_rec["aliases_ko"]) != set(rec.aliases_ko):
                mismatched.append(
                    f"{rec.canonical}: aliases_ko py={sorted(rec.aliases_ko)!r} "
                    f"ts={sorted(ts_rec['aliases_ko'])!r}"
                )
            if set(ts_rec["aliases_en"]) != set(rec.aliases_en):
                mismatched.append(
                    f"{rec.canonical}: aliases_en py={sorted(rec.aliases_en)!r} "
                    f"ts={sorted(ts_rec['aliases_en'])!r}"
                )
        assert not missing, f"canonical records in PY but missing from TS: {missing}"
        assert not mismatched, "field drift between TS and PY records:\n" + "\n".join(mismatched)

    def test_no_ts_records_absent_from_py(self):
        """Catches the opposite drift direction — a TS-only addition that
        never made it back to Python."""
        ts_records = _parse_ts_records()
        py_canonicals = {rec.canonical for rec in ALL_INVESTORS}
        extra = sorted(set(ts_records) - py_canonicals)
        assert not extra, f"canonical records in TS but missing from PY: {extra}"


class TestAliasDenylistSync:
    def test_denylist_keys_match(self):
        ts_denylist = _parse_ts_denylist()
        assert set(ts_denylist.keys()) == set(_ALIAS_DENYLIST.keys()), (
            f"denylist key drift: py={sorted(_ALIAS_DENYLIST)!r} "
            f"ts={sorted(ts_denylist)!r} (see b7d58f5 — this is exactly the "
            "class of drift that fix corrected)"
        )

    def test_denylist_values_match(self):
        ts_denylist = _parse_ts_denylist()
        mismatched = []
        for key, py_values in _ALIAS_DENYLIST.items():
            ts_values = ts_denylist.get(key, ())
            if set(ts_values) != set(py_values):
                mismatched.append(
                    f"{key}: py={sorted(py_values)!r} ts={sorted(ts_values)!r}"
                )
        assert not mismatched, "denylist value drift between TS and PY:\n" + "\n".join(mismatched)
