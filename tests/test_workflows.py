"""Guards against CI workflows that silently pass when they should fail."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def test_ci_does_not_stub_agentprod():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "using stub" not in text
    assert "__init__.py" not in text, "ci.yml must not write a fake agentprod package"


def test_ci_falls_back_to_pypi_agentprod():
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "pip install agentprod" in text


def test_backstop_fails_when_admin_secret_missing():
    text = (WORKFLOWS / "daily-build-backstop.yml").read_text(encoding="utf-8")
    m = re.search(
        r'if \[ -z "\$ADMIN_KEY" \]; then\n(.*?)\n\s*fi\n', text, re.S
    )
    assert m, "missing-secret branch not found"
    branch = m.group(1)
    assert "exit 1" in branch
    assert "exit 0" not in branch
