#!/usr/bin/env python3
"""Container/systemd health probe. Uses PORT, never a spend key."""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

from app.server_boot import bind_address


def main() -> int:
    addr = bind_address()
    url = f"http://127.0.0.1:{addr.port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return 0 if 200 <= int(response.status) < 300 else 1
    except (urllib.error.URLError, TimeoutError, OSError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
