"""集中管理项目内所有路径,便于测试时 monkeypatch。"""
from __future__ import annotations

import os
from pathlib import Path

# 根目录优先读环境变量 HCIQ_ROOT,否则推断为本文件向上第四级
_DEFAULT_ROOT = Path(__file__).resolve().parents[3]
ROOT = Path(os.getenv("HCIQ_ROOT", str(_DEFAULT_ROOT)))

DATA_DIR = ROOT / "data"
TD_RAW_DIR = DATA_DIR / "td" / "raw"
TD_NORMALIZED_DIR = Path(os.getenv("HCIQ_TD_NORMALIZED_DIR", DATA_DIR / "td" / "normalized"))
TD_TASKS_DIR = DATA_DIR / "td" / "tasks"
TEMPLATES_DIR = DATA_DIR / "templates"

LIGHTRAG_DIR = Path(os.getenv("HCIQ_LIGHTRAG_DIR", ROOT / "lightrag_storage"))
KUZU_DIR = Path(os.getenv("HCIQ_KUZU_DIR", DATA_DIR / "codegraph.kuzu"))
SYMBOL_REGISTRY_DB = Path(os.getenv("HCIQ_SYMBOL_REGISTRY", DATA_DIR / "symbols.sqlite"))

MODELS_DIR = ROOT / "models"
BGE_M3_DIR = Path(os.getenv("HCIQ_BGE_M3_DIR", MODELS_DIR / "bge-m3"))

REPOS_DIR = ROOT / "repos"
LOGS_DIR = ROOT / "logs"
TRACES_DIR = ROOT / "traces"
CONFIGS_DIR = ROOT / "configs"


def ensure_dirs() -> None:
    """创建所有运行时依赖目录,幂等。"""
    for d in [
        TD_RAW_DIR, TD_NORMALIZED_DIR, TD_TASKS_DIR, TEMPLATES_DIR,
        LIGHTRAG_DIR, KUZU_DIR.parent,
        LOGS_DIR, TRACES_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)
