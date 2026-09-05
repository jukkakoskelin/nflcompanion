"""Command-line entry point to run the nflcompanion MCP server over stdio."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is in python path
repo_root = Path(__file__).resolve().parent.parent
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from nflcompanion.mcp_server import main

if __name__ == "__main__":
    raise SystemExit(main())
