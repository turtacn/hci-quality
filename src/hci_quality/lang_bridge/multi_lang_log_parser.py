"""多语言日志解析器。为五种语言各自维护一棵 Drain3 模板树,并预填常见错误模式。

用法:
    parser = MultiLangLogParser()
    entry = parser.parse("Traceback (most recent call last): ...", lang_hint=None)
    print(entry.lang, entry.stack_trace)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("hci_quality.lang_bridge.multi_lang_log_parser")

_LANG_SIGNALS = (
    ("python", re.compile(r"(Traceback \(most recent|AttributeError:|KeyError:|File \")")),
    ("java",   re.compile(r"(java\.\w|NullPointerException|SQLException|\.java:\d+|at \w+\.\w+\()")),
    ("go",     re.compile(r"(panic: |goroutine \d+|dial tcp .* connection refused|context deadline exceeded)")),
    ("c",      re.compile(r"(Segmentation fault|malloc:|#\d+\s+0x[0-9a-f]+\s+in)")),
    ("perl",   re.compile(r"(Can't call method|Undefined subroutine|Cannot locate [\w:]+ in @INC|DHCP|UDS)")),
)


@dataclass
class ParsedLogEntry:
    lang: str
    log_level: str = "ERROR"
    error_code: Optional[str] = None
    stack_trace: list[dict] = field(default_factory=list)
    function_calls: list[str] = field(default_factory=list)
    raw_message: str = ""
    template_id: int = -1
    template: str = ""


class _NullMiner:
    """drain3 不可用时的占位 miner。"""

    def add_log_message(self, _line: str) -> dict:
        return {"cluster_id": -1, "template_mined": "", "parameter_list": []}

    def add_template(self, _tmpl: str, _name: str) -> None:
        pass


class MultiLangLogParser:
    _STACK_PATTERNS = {
        "python": re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<fn>[\w.]+)'),
        "java":   re.compile(r'at (?P<cls>[\w.$]+)\.(?P<fn>[\w<>$]+)\((?P<file>[\w.]+):(?P<line>\d+)\)'),
        "go":     re.compile(r'(?P<fn>[\w./]+(?:\.\(\*?\w+\))?\.\w+)\(.*?\)(?:\s*\n\s*(?P<file>[^\s:]+):(?P<line>\d+))?'),
        "perl":   re.compile(r'at (?P<file>[\w./\\]+) line (?P<line>\d+)'),
        "c":      re.compile(r'#\d+\s+0x[0-9a-fA-F]+\s+in\s+(?P<fn>\w+)\s+at\s+(?P<file>[^\s:]+):(?P<line>\d+)'),
    }
    _ERRCODE = {
        "python": re.compile(r'(?:Errno \d+|HTTP \d{3}|grpc\.StatusCode\.\w+)'),
        "java":   re.compile(r'(?:SQLSTATE\[\w+\]|[A-Z]+_\d+)'),
        "go":     re.compile(r'(?:status code: \d+|error #\d+)'),
        "c":      re.compile(r'(?:errno=\d+|0x[0-9a-fA-F]+)'),
        "perl":   re.compile(r'(?:DHCP|ERR|ERROR|TD-?\d+)'),
    }

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir
        self.parsers: dict[str, object] = {}
        try:
            from drain3 import TemplateMiner
            from drain3.template_miner_config import TemplateMinerConfig
            for lang in ("perl", "python", "java", "c", "go"):
                self.parsers[lang] = TemplateMiner(config=TemplateMinerConfig())
        except ImportError:
            log.warning("drain3 not installed; falling back to null miner")
            for lang in ("perl", "python", "java", "c", "go"):
                self.parsers[lang] = _NullMiner()
        self._seed_templates()

    def _seed_templates(self) -> None:
        """预填常见错误模式以加速首屏收敛。"""
        seeds = {
            "perl": [
                "Cannot locate <*> in @INC",
                "Can't call method <*> on unblessed reference",
                "Undefined subroutine <*> called",
                "DHCP timeout on <*> after <*>s",
                "UDS connection refused: <*>",
            ],
            "python": [
                "Traceback (most recent call last):",
                "ConnectionRefusedError: <*>",
                "FileNotFoundError: <*>",
                "KeyError: <*>",
                "AttributeError: <*> object has no attribute <*>",
                "grpc._channel._RpcError: <*>",
            ],
            "java": [
                "java.net.ConnectException: Connection refused",
                "java.sql.SQLException: <*>",
                "java.lang.NullPointerException",
                "io.grpc.StatusRuntimeException: <*>",
            ],
            "c": [
                "ERROR: <*> failed: <*>",
                "Segmentation fault (core dumped)",
                "malloc: cannot allocate <*> bytes",
            ],
            "go": [
                "panic: <*>",
                "failed to <*>: <*>",
                "dial tcp <*>: connection refused",
                "context deadline exceeded",
            ],
        }
        # Drain3 的 add_template 在某些版本不可用;这里忽略异常
        for lang, templates in seeds.items():
            miner = self.parsers.get(lang)
            for t in templates:
                try:
                    miner.add_template(t, f"{lang}-seed")  # type: ignore[attr-defined]
                except Exception:
                    pass

    @classmethod
    def detect_lang(cls, text: str) -> str:
        for lang, pat in _LANG_SIGNALS:
            if pat.search(text):
                return lang
        return "perl"

    def parse(self, log_line: str, lang_hint: Optional[str] = None) -> ParsedLogEntry:
        lang = lang_hint or self.detect_lang(log_line)
        miner = self.parsers.get(lang, self.parsers["perl"])
        try:
            result = miner.add_log_message(log_line)  # type: ignore[attr-defined]
        except Exception:
            result = {"cluster_id": -1, "template_mined": ""}

        stack = self._extract_stack(log_line, lang)
        err = self._extract_error_code(log_line, lang)

        return ParsedLogEntry(
            lang=lang,
            error_code=err,
            stack_trace=stack,
            function_calls=[s["func"] for s in stack if s.get("func")],
            raw_message=log_line,
            template_id=result.get("cluster_id", -1) if isinstance(result, dict) else -1,
            template=result.get("template_mined", "") if isinstance(result, dict) else "",
        )

    def _extract_stack(self, line: str, lang: str) -> list[dict]:
        pat = self._STACK_PATTERNS.get(lang)
        if not pat:
            return []
        out: list[dict] = []
        for m in pat.finditer(line):
            gd = m.groupdict()
            out.append({
                "lang": lang,
                "func": gd.get("fn") or gd.get("cls"),
                "file": gd.get("file"),
                "line": int(gd["line"]) if gd.get("line") else None,
            })
        return out

    def _extract_error_code(self, line: str, lang: str) -> Optional[str]:
        pat = self._ERRCODE.get(lang)
        if not pat:
            return None
        m = pat.search(line)
        return m.group(0) if m else None

    def save_templates(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for lang, miner in self.parsers.items():
            drain = getattr(miner, "drain", None)
            if drain is None:
                continue
            entries = []
            for c in getattr(drain, "clusters", []):
                entries.append({"id": getattr(c, "cluster_id", -1),
                                "template": getattr(c, "get_template", lambda: "")()})
            (output_dir / f"templates_{lang}.json").write_text(
                json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
            )
