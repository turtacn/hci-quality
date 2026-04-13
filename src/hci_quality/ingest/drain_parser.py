"""Drain3 日志模板解析的薄封装,多语言版本请见 lang_bridge.multi_lang_log_parser。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DrainResult:
    template_id: int
    template: str
    parameters: list[str]


class DrainParser:
    """单语言 Drain3 parser,维持向后兼容。"""

    def __init__(self, persistence_file: Path | None = None):
        try:
            from drain3 import TemplateMiner
            from drain3.template_miner_config import TemplateMinerConfig
        except ImportError as e:
            raise RuntimeError("drain3 未安装,请检查 pyproject.toml 依赖") from e

        cfg = TemplateMinerConfig()
        self._miner = TemplateMiner(config=cfg)
        self._persistence_file = persistence_file

    def parse(self, line: str) -> DrainResult:
        r = self._miner.add_log_message(line)
        return DrainResult(
            template_id=r.get("cluster_id", -1),
            template=r.get("template_mined", ""),
            parameters=list(r.get("parameter_list", [])),
        )
