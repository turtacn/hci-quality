"""Phoenix OTEL 引导。每个 MCP server、webhook、评估脚本都应在 main 入口调用 register。"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=None)
def register(project_name: str) -> Any:
    """幂等注册 OTEL tracer provider 到 Phoenix。

    通过 LRU cache 保证同一 project_name 在进程内只注册一次,避免重复 instrumentation。
    失败时不抛异常,返回 None,让上层继续工作 —— 观测降级优先于业务崩溃。
    """
    try:
        from phoenix.otel import register as _phoenix_register
    except ImportError:
        return None

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:6006/v1/traces")
    try:
        return _phoenix_register(
            project_name=project_name,
            endpoint=endpoint,
            auto_instrument=True,
        )
    except Exception:
        return None
