"""Vercel FastAPI entry — Alpha Sentinel API + Mission Control SPA."""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from app.application import app as _app

    app = _app

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _STATIC = _ROOT / "dashboard" / "dist"
    _ASSETS = _STATIC / "assets"
    _INDEX = _STATIC / "index.html"

    if _ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS)), name="assets")

    @app.get("/", include_in_schema=False)
    async def mission_control_root():
        if _INDEX.is_file():
            return FileResponse(str(_INDEX))
        return {
            "service": "Alpha Sentinel MCP Server",
            "status": "operational",
            "mission_control": "static bundle missing — API only",
            "health": "/health",
            "docs": "/docs",
        }

except Exception:  # pragma: no cover
    _boot_error = traceback.format_exc()
    from fastapi import FastAPI, Request

    app = FastAPI(title="Alpha Sentinel BOOT FAILED")

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def boot_failed(request: Request, full_path: str = ""):
        return {
            "error": "boot_failed",
            "path": request.url.path,
            "detail": _boot_error[:6000],
        }
