#!/usr/bin/env python3
"""Alpha Sentinel MCP Server - Stdio Transport Runner.

This script runs the FastMCP server using stdio transport,
allowing IDEs like Cursor, VS Code, and other MCP clients to connect.

Usage:
    python run_stdio.py
    
The server will read from stdin and write to stdout.
"""

import sys
import logging
from app.mcp_server import mcp_app

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Run MCP server via stdio transport."""
    logger.info("🚀 Starting Alpha Sentinel MCP Server (stdio mode)...")
    logger.info(f"📊 Tools available: {len(mcp_app._tool_manager._tools)}")
    
    try:
        # Run the FastMCP server with stdio transport
        mcp_app.run()
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down gracefully...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
