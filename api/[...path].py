"""Catch-all under /api/* — same FastAPI app as index.py."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from app.main import app  # noqa: F401
except Exception as boot_err:  # pragma: no cover
    import traceback
    from fastapi import FastAPI

    app = FastAPI(title="Alpha Sentinel BOOT FAILED")
    _detail = f"{type(boot_err).__name__}: {boot_err}\n{traceback.format_exc()}"

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
    async def _boot_failed(full_path: str = ""):
        return {"error": "boot_failed", "detail": _detail[:4000], "path": full_path}
