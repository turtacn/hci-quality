"""多语言符号注册表。

职责:
  1. 把各语言的原始 qname 归一为 canonical_name(形如 network.dhcp.renew)
  2. 维护 (lang, qname) <-> canonical 的双向索引
  3. 持久化到 SQLite,供 MCP server 与 eval 复用
  4. 导出 YAML 便于审阅与 diff

此模块是 ADR-0006 的落地点,替代原 customer_terms.yaml 的单向手工字典。
"""
from __future__ import annotations

import logging
import re
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from ..utils.paths import CONFIGS_DIR, SYMBOL_REGISTRY_DB

log = logging.getLogger("hci_quality.lang_bridge.symbol_registry")

# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class SymbolVariant:
    lang: str
    qname: str
    file: Optional[str] = None
    line_start: Optional[int] = None
    signature: Optional[str] = None


@dataclass
class UnifiedSymbol:
    canonical_name: str
    domain: str
    semantic_tags: list[str] = field(default_factory=list)
    variants: dict[str, SymbolVariant] = field(default_factory=dict)
    boundary_type: str = "unknown"
    confidence: float = 0.5


# ---------------------------------------------------------------------------
# 各语言 Parser:只负责 qname 归一化,AST 抽取在 graph.tree_sitter_extract
# ---------------------------------------------------------------------------


class LanguageParser(ABC):
    lang_name: str = ""

    @abstractmethod
    def normalize_name(self, raw_qname: str) -> str:
        """把原始 qname 转为跨语言 canonical 形式。"""


class PerlParser(LanguageParser):
    lang_name = "perl"
    MODULE_DOMAIN = {
        "Net": "network", "Storage": "storage", "Auth": "auth",
        "Diag": "diagnostics", "Config": "config", "Log": "logging",
        "DB": "database", "Cache": "cache", "IPC": "ipc", "FS": "filesystem",
        "HCI": "hci", "VCLS": "vcls",
    }

    def normalize_name(self, raw: str) -> str:
        parts = raw.split("::")
        if not parts:
            return raw.lower()
        domain = self.MODULE_DOMAIN.get(parts[0], parts[0].lower())
        tail = ".".join(p.lower() for p in parts[1:]) if len(parts) > 1 else ""
        return f"{domain}.{tail}" if tail else domain


class GoParser(LanguageParser):
    lang_name = "go"
    _RECV = re.compile(r"\(\*?(?P<recv>[A-Za-z_]\w*)\)")

    def normalize_name(self, raw: str) -> str:
        # github.com/hci/net.(*DHCP).Renew -> net.dhcp.renew
        tail = raw.rsplit("/", 1)[-1]
        recv_match = self._RECV.search(tail)
        parts = tail.replace("(*", "").replace(")", "").split(".")
        return ".".join(p.lower() for p in parts if p)


class PythonParser(LanguageParser):
    lang_name = "python"
    MODULE_DOMAIN = {
        "net": "network", "network": "network", "storage": "storage",
        "auth": "auth", "diag": "diagnostics", "config": "config",
        "db": "database", "cache": "cache", "ipc": "ipc", "fs": "filesystem",
        "ml": "ml", "analytics": "analytics", "hci": "hci",
    }

    def normalize_name(self, raw: str) -> str:
        parts = raw.split(".")
        if not parts:
            return raw.lower()
        head = self.MODULE_DOMAIN.get(parts[0].lower(), parts[0].lower())
        return ".".join([head] + [p.lower() for p in parts[1:]])


class JavaParser(LanguageParser):
    lang_name = "java"
    BASE_PACKAGES = ("com", "org", "io", "net", "hci")

    def normalize_name(self, raw: str) -> str:
        # com.hci.network.DHCPService.renew -> network.dhcpservice.renew
        parts = raw.split(".")
        filtered: list[str] = []
        started = False
        for p in parts:
            if not started and p in self.BASE_PACKAGES:
                continue
            started = True
            filtered.append(p.lower())
        return ".".join(filtered) if filtered else raw.lower()


class CParser(LanguageParser):
    lang_name = "c"

    def normalize_name(self, raw: str) -> str:
        # dhcp.c::dhcp_renew -> dhcp.renew
        if "::" in raw:
            file, fn = raw.split("::", 1)
            stem = Path(file).stem.lower()
            fn = fn.lower().lstrip("_")
            # 常见前缀剥离,如 dhcp_renew -> renew(若前缀与文件名相同)
            if fn.startswith(stem + "_"):
                fn = fn[len(stem) + 1:]
            return f"{stem}.{fn}" if fn else stem
        return raw.lower()


_PARSERS: dict[str, LanguageParser] = {
    "perl":   PerlParser(),
    "go":     GoParser(),
    "python": PythonParser(),
    "java":   JavaParser(),
    "c":      CParser(),
}


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------


class SymbolRegistry:
    """双向索引 + SQLite 持久化。

    表结构(宽表 + 倒排):
      symbols (lang TEXT, qname TEXT, canonical TEXT, file TEXT, line_start INT,
               PRIMARY KEY (lang, qname))
      by_canonical 索引自动建立
    """

    def __init__(self, db_path: Path = SYMBOL_REGISTRY_DB):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), isolation_level=None)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                lang TEXT NOT NULL,
                qname TEXT NOT NULL,
                canonical TEXT NOT NULL,
                file TEXT,
                line_start INTEGER,
                PRIMARY KEY (lang, qname)
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_canonical ON symbols(canonical)")

    # -------- 核心 API --------

    @staticmethod
    def canonicalize(lang: str, raw_qname: str) -> str:
        p = _PARSERS.get(lang)
        return p.normalize_name(raw_qname) if p else raw_qname.lower()

    def register(self, lang: str, qname: str, canonical: str,
                 file: str | None = None, line_start: int | None = None) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO symbols(lang, qname, canonical, file, line_start) "
            "VALUES (?, ?, ?, ?, ?)",
            (lang, qname, canonical, file, line_start),
        )

    def lookup(self, lang: str, qname: str) -> Optional[UnifiedSymbol]:
        row = self._conn.execute(
            "SELECT canonical FROM symbols WHERE lang=? AND qname=?",
            (lang, qname),
        ).fetchone()
        if not row:
            return None
        return self.by_canonical(row[0])

    def by_canonical(self, canonical: str) -> UnifiedSymbol:
        rows = self._conn.execute(
            "SELECT lang, qname, file, line_start FROM symbols WHERE canonical=?",
            (canonical,),
        ).fetchall()
        domain = canonical.split(".")[0] if "." in canonical else "unknown"
        sym = UnifiedSymbol(canonical_name=canonical, domain=domain)
        for lang, qn, f, ln in rows:
            sym.variants[lang] = SymbolVariant(lang=lang, qname=qn, file=f, line_start=ln)
        sym.confidence = min(1.0, 0.4 + 0.15 * len(sym.variants))
        return sym

    def cross_lang_edges(self, lang_a: str, lang_b: str) -> list[tuple[str, str, str]]:
        rows = self._conn.execute(
            """SELECT a.qname, b.qname, a.canonical
               FROM symbols a JOIN symbols b
                 ON a.canonical = b.canonical
               WHERE a.lang=? AND b.lang=?""",
            (lang_a, lang_b),
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

    def stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for lang, cnt in self._conn.execute(
            "SELECT lang, COUNT(*) FROM symbols GROUP BY lang"
        ).fetchall():
            stats[lang] = cnt
        stats["total"] = sum(stats.values())
        stats["canonical_unique"] = self._conn.execute(
            "SELECT COUNT(DISTINCT canonical) FROM symbols"
        ).fetchone()[0]
        return stats

    # -------- 持久化 / 导出 --------

    def persist(self) -> None:
        """SQLite isolation_level=None 下已自动提交,本方法只用于显式 flush。"""
        self._conn.commit()

    def dump_yaml(self, path: Path) -> int:
        by_c: dict[str, dict] = {}
        for lang, qn, canonical, _f, _l in self._conn.execute(
            "SELECT lang, qname, canonical, file, line_start FROM symbols"
        ):
            entry = by_c.setdefault(canonical, {
                "canonical": canonical,
                "domain": canonical.split(".")[0] if "." in canonical else "unknown",
            })
            entry[lang] = qn
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(by_c, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        return len(by_c)

    def close(self) -> None:
        self._conn.close()

    # -------- 单例入口 --------

    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> "SymbolRegistry":
        return cls()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, help="dump YAML snapshot to path")
    ap.add_argument("--stats", action="store_true", help="print stats JSON")
    args = ap.parse_args()

    reg = SymbolRegistry.load()
    if args.dump:
        n = reg.dump_yaml(args.dump)
        print(f"dumped {n} canonical symbols to {args.dump}")
    if args.stats:
        import json
        print(json.dumps(reg.stats(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
