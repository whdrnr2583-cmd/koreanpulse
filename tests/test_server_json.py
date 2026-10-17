"""server.json (MCP registry definition) consistency checks. Offline only.

Schema validation against the $schema URL was run by hand on 2026-10-17 and passed.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _server():
    return json.loads((ROOT / "server.json").read_text(encoding="utf-8"))


def _pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)


def test_hosted_endpoint_not_advertised():
    # Hosting is stopped (owner decision 2026-10-06); the registry must not point at it.
    assert "remotes" not in _server()


def test_pypi_package_entry():
    data = _server()
    (pkg,) = data["packages"]
    assert pkg["registryType"] == "pypi"
    assert pkg["identifier"] == "koreanpulse"
    assert pkg["transport"] == {"type": "stdio"}


def test_versions_match_pyproject():
    data = _server()
    assert data["version"] == _pyproject_version()
    assert data["packages"][0]["version"] == _pyproject_version()
