"""Intelligence + quota timestamps must be timezone-aware UTC (no utcnow)."""

from __future__ import annotations

import pathlib
import re

from app.commerce import CommerceLayer


def test_no_utcnow_in_app():
    hits = [
        str(p)
        for p in pathlib.Path("app").rglob("*.py")
        if re.search(r"datetime\.utcnow\(", p.read_text(encoding="utf-8"))
    ]
    assert hits == []


def test_quota_reset_is_aware_utc():
    from app.config import settings

    q = CommerceLayer(settings).get_quota("agent-x")
    assert q.reset_at is not None
    assert q.reset_at.tzinfo is not None
    assert q.reset_at.utcoffset().total_seconds() == 0
