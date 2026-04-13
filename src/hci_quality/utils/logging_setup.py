"""统一日志引导。MCP stdio server 必须让所有 stdout 保持纯净,日志走 stderr 或文件。"""
from __future__ import annotations

import logging
import logging.config
import sys
from pathlib import Path

import yaml

from .paths import CONFIGS_DIR, LOGS_DIR


def setup_logging(service_name: str = "hci_quality", *, stdio_safe: bool = False) -> logging.Logger:
    """加载 configs/logging.yaml 并返回一个 logger。

    参数
    ----
    service_name: 日志命名空间。
    stdio_safe: 当本进程是 MCP stdio server 时必须为 True,所有 handler 强制写 stderr。
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    cfg_path = CONFIGS_DIR / "logging.yaml"
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        if stdio_safe:
            for h in cfg.get("handlers", {}).values():
                if h.get("class") == "logging.StreamHandler":
                    h["stream"] = "ext://sys.stderr"
        logging.config.dictConfig(cfg)
    else:
        logging.basicConfig(
            level=logging.INFO,
            stream=sys.stderr,
            format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        )
    return logging.getLogger(service_name)
