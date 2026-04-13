"""MCP stdio server: codegraph.query / query_by_canonical / cross_language_hop"""
from __future__ import annotations

import sys

from ..lang_bridge.multi_lang_graph import MultiLangGraph
from ..lang_bridge.symbol_registry import SymbolRegistry
from ..obs.phoenix_bootstrap import register
from ..utils.logging_setup import setup_logging
from ..utils.paths import KUZU_DIR
from ._common import safe_tool

_graph: MultiLangGraph | None = None


def _g() -> MultiLangGraph:
    global _graph
    if _graph is None:
        _graph = MultiLangGraph(str(KUZU_DIR))
    return _graph


def _build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        print(f"mcp SDK not available: {e}", file=sys.stderr)
        sys.exit(2)

    server = FastMCP("codegraph")

    @server.tool()
    @safe_tool("codegraph.query")
    def codegraph_query(qname: str, lang: str = "perl",
                        direction: str = "callers", depth: int = 2) -> dict:
        """查询给定函数的调用者或被调用者。

        参数:
          qname:     函数全限定名
          lang:      所属语言 perl|go|python|java|c
          direction: 'callers' 或 'callees'
          depth:     跳数,默认 2,最大 5
        返回:
          {"results": [...]}
        """
        depth = max(1, min(int(depth), 5))
        return {"results": _g().query_function(lang, qname, direction, depth)}

    @server.tool()
    @safe_tool("codegraph.query_by_canonical")
    def codegraph_query_by_canonical(canonical: str) -> dict:
        """通过 canonical_name 查询所有语言变体。"""
        rows = _g().query_by_canonical(canonical)
        reg_hit = SymbolRegistry.load().by_canonical(canonical)
        return {
            "canonical": canonical,
            "graph_hits": rows,
            "variants": {lang: {"qname": v.qname, "file": v.file, "line_start": v.line_start}
                         for lang, v in reg_hit.variants.items()},
            "confidence": reg_hit.confidence,
        }

    @server.tool()
    @safe_tool("codegraph.cross_language_hop")
    def codegraph_cross_language_hop(from_qname: str, from_lang: str,
                                     target_langs: list[str] | None = None) -> dict:
        """从某语言的 qname 跳到其他语言的对应实现。

        工作流:SymbolRegistry 查 canonical → 取其余语言 variants。
        """
        reg = SymbolRegistry.load()
        sym = reg.lookup(from_lang, from_qname)
        if sym is None:
            return {"candidates": [], "reason": "symbol not registered; run kuzu_build first"}
        wanted = set(target_langs or [])
        out = []
        for lang, v in sym.variants.items():
            if lang == from_lang:
                continue
            if wanted and lang not in wanted:
                continue
            out.append({
                "lang": lang,
                "qname": v.qname,
                "canonical": sym.canonical_name,
                "confidence": sym.confidence,
                "file": v.file,
            })
        return {"candidates": out, "canonical": sym.canonical_name}

    return server


def main() -> None:
    setup_logging("mcp-codegraph", stdio_safe=True)
    register("mcp-codegraph")
    server = _build_server()
    server.run()


if __name__ == "__main__":
    main()
