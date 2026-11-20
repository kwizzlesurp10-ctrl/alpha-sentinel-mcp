#!/usr/bin/env python3
"""Alpha Sentinel MCP Server - Stdio Transport Runner.

This script runs the FastMCP server using stdio transport,
allowing IDEs like Cursor, VS Code, and other MCP clients to connect.

Usage:
    python run_stdio.py
    
The server will read from stdin and write to stdout.
"""

import logging
import os
import sys

os.environ.setdefault("FASTMCP_SHOW_CLI_BANNER", "false")

from app.mcp_server import mcp_app

# Setup logging (MUST use stderr so stdout stays pure JSON-RPC for MCP stdio)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Run MCP server via stdio transport."""
    logger.info("Starting Alpha Sentinel MCP Server (stdio mode)...")

    try:
        try:
            mcp_app.run(show_banner=False)
        except TypeError:
            mcp_app.run()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
