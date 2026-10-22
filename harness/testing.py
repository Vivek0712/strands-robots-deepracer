"""Small helpers the QA tests share: read a Strands tool result as text, arm the car over rosbridge.

Kept in the harness package rather than in `tests/conftest.py` because pytest's importlib mode
does not expose `conftest` as an importable module name.
"""

from __future__ import annotations

from typing import Any


def result_text(result: dict[str, Any]) -> str:
    """The joined text of a Strands tool result ``{"status", "content": [{"text"}]}``."""
    return " ".join(c.get("text", "") for c in result.get("content", []))


__all__ = ["result_text"]
