"""从 TD 自由文本中抽取堆栈帧与错误码。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class StackFrame:
    lang: str
    qname: str
    file: Optional[str] = None
    line: Optional[int] = None


# 各语言堆栈帧的正则,精确优先
_PATTERNS = {
    "python": re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<fn>[\w.]+)'),
    "java":   re.compile(r'at (?P<cls>[\w.$]+)\.(?P<fn>[\w<>$]+)\((?P<file>[\w.]+):(?P<line>\d+)\)'),
    "go":     re.compile(r'(?P<fn>[\w./]+(?:\.\(\*?\w+\))?\.\w+)\(.*?\)\s*\n\s*(?P<file>[^\s:]+):(?P<line>\d+)'),
    "perl":   re.compile(r'at (?P<file>[\w./\\]+) line (?P<line>\d+)(?:, <[^>]+>)?'),
    "c":      re.compile(r'#\d+\s+0x[0-9a-fA-F]+\s+in\s+(?P<fn>\w+)\s+at\s+(?P<file>[^\s:]+):(?P<line>\d+)'),
}

_ERRCODE = re.compile(
    r'(?:errno=\d+|0x[0-9a-fA-F]+|HTTP \d{3}|SQLSTATE\[\w+\]|'
    r'grpc\.StatusCode\.\w+|panic: [^\n]+|Segmentation fault|'
    r'TD-\d+)'
)


def extract_frames(text: str) -> list[StackFrame]:
    """混合多语言堆栈抽取;按出现位置返回。"""
    out: list[StackFrame] = []
    for lang, pat in _PATTERNS.items():
        for m in pat.finditer(text):
            gd = m.groupdict()
            out.append(StackFrame(
                lang=lang,
                qname=gd.get("fn") or gd.get("cls", "") or "",
                file=gd.get("file"),
                line=int(gd["line"]) if gd.get("line") else None,
            ))
    return out


def extract_error_codes(text: str) -> list[str]:
    return list(dict.fromkeys(_ERRCODE.findall(text)))


def extract_qnames(text: str) -> list[str]:
    """堆栈帧归一为 qname 列表,保留语言前缀以便下游区分。"""
    return [f"{f.lang}::{f.qname}" for f in extract_frames(text) if f.qname]
