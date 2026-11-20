#!/usr/bin/env python3
"""Alpha Sentinel MCP Server - Stdio JSON-RPC 2.0 Transport Runner.

Speaks pure newline-delimited JSON-RPC 2.0 over stdin/stdout without requiring
external CLI banners or optional fastmcp wrappers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from app.tools_registry import TOOL_SPECS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-03-26"
SERVER_NAME = "alpha-sentinel"
SERVER_VERSION = "0.2.1"

_WRITE_TOOLS = frozenset({"tokenized_stock_seal_receipt"})


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _tool_annotations(spec: dict[str, Any]) -> dict[str, Any]:
    """Return MCP ToolAnnotations describing read-only vs write/external behavior."""
    name = spec["name"]
    is_write = name in _WRITE_TOOLS
    return {
        "title": name.replace("_", " ").title(),
        "readOnlyHint": not is_write,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }


def _tools_list() -> list[dict[str, Any]]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"].strip(),
            "inputSchema": spec["inputSchema"],
            "annotations": _tool_annotations(spec),
        }
        for spec in TOOL_SPECS
    ]


async def _handle_request(req: dict[str, Any]) -> None:
    method = req.get("method")
    req_id = req.get("id")
    if method == "notifications/initialized" or req_id is None:
        return

    if method == "initialize":
        client_ver = (req.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION
        _write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": client_ver,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": (
                        "Alpha Sentinel market intelligence over x402 on Base. "
                        "Paid tools settle in USDC on Base mainnet (eip155:8453)."
                    ),
                },
            }
        )
        return

    if method == "tools/list":
        _write({"jsonrpc": "2.0", "id": req_id, "result": {"tools": _tools_list()}})
        return

    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name", "")
        arguments = params.get("arguments") or {}
        meta = params.get("_meta") or params.get("meta")
        try:
            from app.mcp_http import call_tool

            res = await call_tool(
                str(name),
                arguments if isinstance(arguments, dict) else {},
                meta if isinstance(meta, dict) else None,
            )
            _write({"jsonrpc": "2.0", "id": req_id, "result": res})
        except Exception as exc:
            _write(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "isError": True,
                        "content": [{"type": "text", "text": str(exc)}],
                    },
                }
            )
        return

    _write(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    )


async def _serve() -> None:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(req, dict):
            await _handle_request(req)


def main() -> None:
    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
