"""Kuzu 图库构建入口。

- schema 由 lang_bridge.multi_lang_graph 统一定义
- 本模块做"解析 → 写入 → 可重入"的编排工作
- 提供 query() 便捷函数供冒烟脚本调用
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import click

from ..lang_bridge.multi_lang_graph import MultiLangGraph
from ..lang_bridge.symbol_registry import SymbolRegistry
from ..utils.logging_setup import setup_logging
from ..utils.paths import KUZU_DIR, REPOS_DIR, ensure_dirs
from .tree_sitter_extract import extract

log = logging.getLogger("hci_quality.graph.kuzu_build")


@lru_cache(maxsize=1)
def _graph() -> MultiLangGraph:
    return MultiLangGraph(str(KUZU_DIR))


def query(cypher: str) -> list[dict]:
    """供冒烟脚本使用的便捷只读查询。"""
    return _graph().raw_query(cypher)


def build(source: Path, lang: str, incremental: bool = False) -> None:
    g = _graph()
    registry = SymbolRegistry.load()

    if not incremental:
        g.reset_schema()

    functions, calls, imports = extract(lang, source)
    log.info("upserting lang=%s functions=%d", lang, len(functions))
    for f in functions:
        canonical = registry.canonicalize(lang, f.qname)
        g.upsert_function(
            lang=f.lang,
            qname=f.qname,
            canonical_name=canonical,
            file=f.file,
            line_start=f.line_start,
            line_end=f.line_end,
            domain=canonical.split(".")[0] if "." in canonical else "unknown",
        )
        registry.register(lang, f.qname, canonical, file=f.file, line_start=f.line_start)

    for c in calls:
        g.upsert_call(lang=c.lang, caller_qname=c.caller_qname,
                      callee_qname=c.callee_name, line_no=c.line)

    registry.persist()
    log.info("build done for lang=%s", lang)


@click.command()
@click.option("--source", type=click.Path(path_type=Path), required=True)
@click.option("--language", type=click.Choice(["perl", "go", "python", "java", "c"]), required=True)
@click.option("--incremental", is_flag=True)
def cli(source: Path, language: str, incremental: bool) -> None:
    setup_logging("hci_quality.graph.kuzu_build")
    ensure_dirs()
    build(source, language, incremental=incremental)


if __name__ == "__main__":
    cli()
