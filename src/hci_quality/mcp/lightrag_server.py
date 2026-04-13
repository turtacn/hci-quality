"""MCP stdio server: lightrag.search"""
from __future__ import annotations

import sys

from ..ingest.lightrag_adapter import search
from ..obs.phoenix_bootstrap import register
from ..utils.logging_setup import setup_logging
from ._common import safe_tool


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        print(f"mcp SDK not available: {e}", file=sys.stderr)
        sys.exit(2)

    server = FastMCP("lightrag")

    @server.tool()
    @safe_tool("lightrag.search")
    def lightrag_search(query: str, top_k: int = 5, mode: str = "hybrid") -> dict:
        """语义检索历史 TD。

        参数:
          query: 检索词,建议是 customer_terms 归一后的词干
          top_k: 返回条数,默认 5
          mode:  'hybrid' | 'local' | 'global' | 'naive'
        返回:
          {"results": [{td_id, score, snippet, metadata}, ...]}
        """
        return {"results": search(query, top_k=top_k, mode=mode)}

    return server


def main() -> None:
    setup_logging("mcp-lightrag", stdio_safe=True)
    register("mcp-lightrag")
    server = _build_server()
    server.run()


if __name__ == "__main__":
    main()
