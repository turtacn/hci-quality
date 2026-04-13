"""客户语言归一字典加载器。"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml

from ..utils.paths import CONFIGS_DIR


@dataclass
class Term:
    canonical: str
    aliases: list[str] = field(default_factory=list)
    owner_module: str = "Unknown"


class TermDict:
    """在 ingest 阶段用于客户语言到 canonical 的映射。

    查询是按最长别名优先匹配,不做正则,避免误伤。
    """

    def __init__(self, terms: list[Term]):
        self._terms = terms
        self._by_alias: dict[str, Term] = {}
        for t in terms:
            for a in t.aliases:
                self._by_alias[a.lower()] = t
            self._by_alias[t.canonical.lower()] = t
        # 从长到短排序,保证"HA agent down"优先于"HA"
        self._alias_keys = sorted(self._by_alias.keys(), key=len, reverse=True)

    def match(self, text: str) -> list[Term]:
        """返回 text 中命中的所有 term,去重保序。"""
        lower = text.lower()
        hit: list[Term] = []
        seen: set[str] = set()
        for k in self._alias_keys:
            if k in lower and self._by_alias[k].canonical not in seen:
                hit.append(self._by_alias[k])
                seen.add(self._by_alias[k].canonical)
        return hit

    def owner_of(self, canonical: str) -> str:
        for t in self._terms:
            if t.canonical == canonical:
                return t.owner_module
        return "Unknown"

    def all(self) -> Iterable[Term]:
        return iter(self._terms)


@lru_cache(maxsize=1)
def load_default() -> TermDict:
    path = CONFIGS_DIR / "customer_terms.yaml"
    return load_from(path)


def load_from(path: Path) -> TermDict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    terms = [
        Term(
            canonical=item["canonical"],
            aliases=list(item.get("aliases", [])),
            owner_module=item.get("owner_module", "Unknown"),
        )
        for item in data
    ]
    return TermDict(terms)
