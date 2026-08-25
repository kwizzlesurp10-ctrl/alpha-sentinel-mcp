"""Vercel FastAPI entry — full Alpha Sentinel API + Mission Control SPA."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.application import app  # noqa: E402, F401

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


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """SPA fallback for client-side routes — skip real API prefixes."""
    # If this was a real API miss, return JSON 404-ish rather than HTML.
    api_prefixes = (
        "health",
        "stats",
        "doctor",
        "wallet",
        "pulse",
        "tools",
        "quota",
        "ledger",
        "swarm",
        "docs",
        "redoc",
        "openapi.json",
        "mcp",
        ".well-known",
        "api",
        "assets",
    )
    head = full_path.split("/", 1)[0]
    if head in api_prefixes or full_path.startswith(".well-known"):
        return {
            "error": "not_found",
            "path": f"/{full_path}",
            "hint": "See /docs for available routes",
        }
    if _INDEX.is_file():
        return FileResponse(str(_INDEX))
    return {"error": "not_found", "path": f"/{full_path}"}
