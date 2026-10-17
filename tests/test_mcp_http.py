"""Regression tests for `koreanpulse.mcp_http`'s import-order invariant.

Commit 3ac65b3 established that `logging.basicConfig()` MUST execute
before `from koreanpulse.server import mcp` — otherwise the default root
logger latches at WARNING before `koreanpulse.server`'s per-tool
`tool_call` INFO instrumentation ever runs, and those log lines are
silently swallowed instead of reaching stderr / mcp.log.

That log is the judgment evidence for the ongoing 30-day AEO
instrumentation (external tools/list / tool_call activity), so a future
refactor that silently reorders these two statements would invalidate
the measurement without any test failing. This file pins the order two
ways:

  1. Static: parse the source and assert the `logging.basicConfig(`
     call appears strictly before the `from koreanpulse.server import`
     line (catches any reordering regardless of runtime import caching).
  2. Behavioral: run the actual sequence dependency in a subprocess (so
     module-level side effects can't leak from a prior import elsewhere
     in the test session) and confirm an INFO-level log from
     `koreanpulse.server`'s logger reaches the root handler once
     `mcp_http` has been imported.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

MCP_HTTP_PATH = Path(__file__).resolve().parent.parent / "src" / "koreanpulse" / "mcp_http.py"


def _source_lines() -> list[str]:
    return MCP_HTTP_PATH.read_text(encoding="utf-8").splitlines()


class TestBasicConfigOrderStatic:
    """Parse the source directly — doesn't depend on Python's import
    cache, so it still catches a reorder even if some other test module
    already imported `koreanpulse.server` first in the same process."""

    def _line_index(self, needle: str) -> int:
        lines = _source_lines()
        for i, line in enumerate(lines):
            if needle in line:
                return i
        raise AssertionError(f"expected line containing {needle!r} not found in {MCP_HTTP_PATH}")

    def test_basicconfig_call_present(self):
        idx = self._line_index("logging.basicConfig(")
        assert idx >= 0

    def test_server_import_present(self):
        idx = self._line_index("from koreanpulse.server import mcp")
        assert idx >= 0

    def test_basicconfig_precedes_server_import(self):
        basicconfig_idx = self._line_index("logging.basicConfig(")
        server_import_idx = self._line_index("from koreanpulse.server import mcp")
        assert basicconfig_idx < server_import_idx, (
            "logging.basicConfig() must appear before `from koreanpulse.server "
            "import mcp` — otherwise tool_call INFO logs are swallowed by the "
            "default WARNING-level root logger (regression of commit 3ac65b3)"
        )

    def test_no_starlette_import_precedes_basicconfig(self):
        """The starlette imports also carry `noqa: E402 — must follow
        basicConfig above` comments; make sure none of them sneak ahead
        of the basicConfig call either (they don't gate the tool_call
        logger, but a reorder here would be a sign the whole block moved)."""
        basicconfig_idx = self._line_index("logging.basicConfig(")
        lines = _source_lines()
        for i, line in enumerate(lines[:basicconfig_idx]):
            assert "import starlette" not in line
            assert "from starlette" not in line


class TestBasicConfigOrderBehavioral:
    """Actually exercise the ordering in a fresh subprocess so we don't
    depend on / pollute this test session's already-imported modules."""

    def test_tool_call_info_log_reaches_root_once_mcp_http_imported(self):
        script = textwrap.dedent(
            """
            import io
            import logging
            import os

            os.environ.setdefault("DART_API_KEY", "dummy")

            # Import mcp_http exactly like a real deployment would (via
            # `uvicorn koreanpulse.mcp_http:app`) — this is what runs
            # logging.basicConfig() before koreanpulse.server is imported.
            import koreanpulse.mcp_http  # noqa: F401

            # basicConfig() already attached a StreamHandler to the root
            # logger pointed at stderr; swap in a buffer we control so we
            # can assert on captured output deterministically.
            buf = io.StringIO()
            handler = logging.StreamHandler(buf)
            handler.setFormatter(logging.Formatter("%(name)s %(levelname)s: %(message)s"))
            root = logging.getLogger()
            root.addHandler(handler)

            logger = logging.getLogger("koreanpulse.server")
            logger.info("tool_call test_tool")

            output = buf.getvalue()
            assert "tool_call test_tool" in output, f"INFO log was swallowed: {output!r}"
            assert "INFO" in output
            print("PASS")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(MCP_HTTP_PATH.parent.parent.parent),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"subprocess failed\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_reversed_order_would_swallow_info_log(self):
        """Negative control — proves the assertion above is actually
        sensitive to ordering, not just always-true. Reproduces the
        *broken* order (import `koreanpulse.server` — and thus fire its
        `logger.info(...)` tool_call instrumentation — before anything
        has called `logging.basicConfig()`) and confirms an INFO record
        emitted at that point is filtered out (root logger's default
        effective level is WARNING until basicConfig configures it),
        i.e. exactly the swallowing bug commit 3ac65b3 fixed."""
        script = textwrap.dedent(
            """
            import logging
            import os

            os.environ.setdefault("DART_API_KEY", "dummy")

            # Broken order: koreanpulse.server (and any tool_call logging
            # it does at import/call time) runs before basicConfig — no
            # handler/level has been configured on the root logger yet.
            import koreanpulse.server  # noqa: F401

            logger = logging.getLogger("koreanpulse.server")
            print("is_info_enabled_before_basicConfig=%s" % logger.isEnabledFor(logging.INFO))
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(MCP_HTTP_PATH.parent.parent.parent),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"subprocess failed\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        # Before basicConfig() has run, the root logger's effective level
        # is WARNING, so an INFO-level tool_call log is not enabled —
        # i.e. it would be dropped, reproducing the pre-3ac65b3 bug.
        assert "is_info_enabled_before_basicConfig=False" in result.stdout


class TestHttpLibraryLogLevels:
    """httpx logs request URLs at INFO and DART URLs carry the API key, so
    the HTTP client loggers must stay quiet while tool_call INFO logs from
    koreanpulse.server keep reaching mcp.log (AEO instrumentation)."""

    def test_httpx_quiet_and_tool_call_logging_kept(self):
        script = textwrap.dedent(
            """
            import logging
            import os

            os.environ.setdefault("DART_API_KEY", "dummy")

            import koreanpulse.mcp_http  # noqa: F401

            assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
            assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
            assert logging.getLogger("koreanpulse.server").isEnabledFor(logging.INFO)
            print("PASS")
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(MCP_HTTP_PATH.parent.parent.parent),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"subprocess failed\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        assert "PASS" in result.stdout


class TestRootBannerAdvertisesActualAddress:
    """The `/` banner must point at the address the caller actually reached,
    not at the first-party hosted endpoint (paused since 2026-09-21)."""

    def _get_root(self, base_url: str) -> str:
        script = textwrap.dedent(
            f"""
            import os
            os.environ.setdefault("DART_API_KEY", "dummy")
            from starlette.testclient import TestClient
            from koreanpulse.mcp_http import app
            resp = TestClient(app, base_url={base_url!r}).get("/")
            assert resp.status_code == 200, resp.status_code
            print(resp.text)
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
        return result.stdout

    def test_banner_uses_local_address_not_hosted_url(self):
        body = self._get_root("http://127.0.0.1:8400")
        assert "http://127.0.0.1:8400/mcp" in body
        assert "mcp.koreanpulse.dev" not in body

    def test_banner_follows_the_requested_host(self):
        body = self._get_root("http://localhost:9999")
        assert "http://localhost:9999/mcp" in body


class TestStartupGuardRejectsDatabaseUrl:
    """With enforced licensing the HTTP entry applies the same rule as
    `server.main`: a set DATABASE_URL is rejected (Postgres store removed)."""

    def _import_mcp_http(self, env: dict) -> subprocess.CompletedProcess:
        import os

        base = {k: v for k, v in os.environ.items()
                if k not in ("DATABASE_URL", "KOREANPULSE_VALIDATE_URL",
                             "KOREANPULSE_CACHE_SHARED_SECRET", "KOREANPULSE_REQUIRE_LICENSE")}
        base["DART_API_KEY"] = "dummy"
        base.update(env)
        return subprocess.run(
            [sys.executable, "-c", "import koreanpulse.mcp_http"],
            capture_output=True, text=True, env=base, timeout=30,
        )

    def test_database_url_is_rejected_when_license_required(self):
        result = self._import_mcp_http({
            "KOREANPULSE_REQUIRE_LICENSE": "1",
            "DATABASE_URL": "postgres://u:p@localhost/db",
            "KOREANPULSE_VALIDATE_URL": "https://example.invalid/v1/validate",
            "KOREANPULSE_CACHE_SHARED_SECRET": "x",
        })
        assert result.returncode != 0
        assert "RuntimeError" in result.stderr
        assert "removed 2026-10-18" in result.stderr
        assert "KOREANPULSE_VALIDATE_URL" in result.stderr

    def test_validate_path_without_database_url_starts(self):
        result = self._import_mcp_http({
            "KOREANPULSE_REQUIRE_LICENSE": "1",
            "KOREANPULSE_VALIDATE_URL": "https://example.invalid/v1/validate",
            "KOREANPULSE_CACHE_SHARED_SECRET": "x",
        })
        assert result.returncode == 0, result.stderr

    def test_database_url_ignored_by_startup_guard_in_dev_mode(self):
        result = self._import_mcp_http({"DATABASE_URL": "postgres://u:p@localhost/db"})
        assert result.returncode == 0, result.stderr
