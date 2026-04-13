"""MCP stdio server: td.read_normalized"""
from __future__ import annotations

import json
import sys

from ..obs.phoenix_bootstrap import register
from ..utils.logging_setup import setup_logging
from ..utils.paths import TD_NORMALIZED_DIR
from ._common import err, safe_tool


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        print(f"mcp SDK not available: {e}", file=sys.stderr)
        sys.exit(2)

    server = FastMCP("td")

    @server.tool()
    @safe_tool("td.read_normalized")
    def td_read_normalized(td_id: str) -> dict:
        """读取一条标准化 TD JSON。"""
        if not td_id:
            return err("BAD_INPUT", "td_id required", "提供非空 td_id")
        path = TD_NORMALIZED_DIR / f"{td_id}.json"
        if not path.exists():
            return err("NOT_FOUND", f"TD {td_id} not normalized yet",
                       "先运行 hci_quality.ingest.td_normalize")
        return json.loads(path.read_text(encoding="utf-8"))

    return server


def main() -> None:
    setup_logging("mcp-td", stdio_safe=True)
    register("mcp-td")
    server = _build_server()
    server.run()


if __name__ == "__main__":
    main()
