"""基于 tree-sitter-languages 的多语言 AST 抽取。

职责:输入源码文件 → 输出 [Function, Call, Import] 三类事实。
不负责写入 Kuzu,交由 kuzu_build 消费。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

log = logging.getLogger("hci_quality.graph.tree_sitter_extract")


@dataclass(frozen=True)
class FunctionFact:
    lang: str
    qname: str
    file: str
    line_start: int
    line_end: int


@dataclass(frozen=True)
class CallFact:
    lang: str
    caller_qname: str
    callee_name: str     # 可能尚未解析到全限定,留给 SymbolRegistry 二次解析
    file: str
    line: int


@dataclass(frozen=True)
class ImportFact:
    lang: str
    importer_file: str
    imported: str


_LANG_GLOB = {
    "perl":   ("*.pm", "*.pl"),
    "go":     ("*.go",),
    "python": ("*.py",),
    "java":   ("*.java",),
    "c":      ("*.c", "*.h"),
}


def _get_parser(lang: str):
    from tree_sitter_languages import get_parser
    return get_parser(lang)


def extract(lang: str, repo_root: Path) -> tuple[list[FunctionFact], list[CallFact], list[ImportFact]]:
    """对单一语言仓库抽取事实。

    本函数是骨架:具体 AST 节点名在各 grammar 版本间会有差异,实现方需按 tree-sitter
    queries 细化。默认返回空,以保证上层 kuzu_build 在 grammar 缺失时不崩溃。
    """
    if lang not in _LANG_GLOB:
        log.warning("unsupported language: %s", lang)
        return [], [], []

    try:
        parser = _get_parser(lang)
    except Exception as e:
        log.warning("tree-sitter parser for %s not available: %s", lang, e)
        return [], [], []

    functions: list[FunctionFact] = []
    calls: list[CallFact] = []
    imports: list[ImportFact] = []

    for pattern in _LANG_GLOB[lang]:
        for src in repo_root.rglob(pattern):
            try:
                data = src.read_bytes()
                tree = parser.parse(data)
            except Exception as e:
                log.debug("skip %s: %s", src, e)
                continue

            # 该处需要针对各语言 AST 节点类型做递归/query。这里给出占位接口,
            # 具体查询编写建议放在 queries/{lang}.scm,通过 tree-sitter Query 加载。
            _walk_and_collect(tree.root_node, lang, str(src), functions, calls, imports, data)

    log.info("lang=%s files=%d functions=%d calls=%d imports=%d",
             lang, sum(1 for _ in repo_root.rglob(_LANG_GLOB[lang][0])),
             len(functions), len(calls), len(imports))
    return functions, calls, imports


def _walk_and_collect(node, lang: str, file: str,
                      functions: list, calls: list, imports: list, src_bytes: bytes) -> None:
    """递归遍历 AST。当前为最小可用实现,实际项目按需完善每种节点类型。"""
    # 只收集明确命名的函数定义,防止把匿名 block 当作函数。
    type_name = getattr(node, "type", "")
    if type_name in {"function_definition", "function_declaration", "method_declaration",
                     "sub_definition", "subroutine_declaration_statement"}:
        # 尝试提取函数名子节点
        name = _find_identifier(node, src_bytes)
        if name:
            functions.append(FunctionFact(
                lang=lang,
                qname=name,   # 真正的 qname 由 SymbolRegistry 再次标准化
                file=file,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
            ))
    # 递归
    for child in getattr(node, "children", []) or []:
        _walk_and_collect(child, lang, file, functions, calls, imports, src_bytes)


def _find_identifier(node, src_bytes: bytes) -> str | None:
    for child in getattr(node, "children", []) or []:
        if child.type in {"identifier", "name", "simple_identifier"}:
            try:
                return src_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
            except Exception:
                return None
    return None


def iter_source_files(repo_root: Path, lang: str) -> Iterator[Path]:
    for pattern in _LANG_GLOB.get(lang, ()):
        yield from repo_root.rglob(pattern)
