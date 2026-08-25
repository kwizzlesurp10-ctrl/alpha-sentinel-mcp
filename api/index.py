"""Vercel Python serverless entry — exports FastAPI ASGI app.

All API traffic is rewritten here (see vercel.json). Static Mission Control
is served from dashboard/dist; same-origin dashboard calls hit these routes.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repo root is on path so `app.*` imports resolve in the serverless bundle.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.main import app  # noqa: E402  — ASGI app discovered by Vercel Python runtime
