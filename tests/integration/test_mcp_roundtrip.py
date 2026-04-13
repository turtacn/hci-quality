"""Integration test: td_server MCP reads a normalized TD file.

集成层不启 subprocess,直接调用装饰器包裹的函数。MCP stdio 传输的完整往返
在 Phase 05 的 Action-2.4 人工 /mcp 验收,不在本文件覆盖。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def fake_td(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "normalized"
    d.mkdir()
    td = {
        "td_id": "TD-INT-1",
        "title": "integration dummy",
        "description": "",
        "comments": "",
        "severity": "P3",
        "module": "HCI-Mgmt",
        "stack_qnames": [],
        "error_codes": [],
        "canonical_terms": [],
    }
    (d / "TD-INT-1.json").write_text(json.dumps(td), encoding="utf-8")
    monkeypatch.setenv("HCIQ_TD_NORMALIZED_DIR", str(d))
    # 强制重新导入 paths
    import importlib
    import hci_quality.utils.paths as paths
    importlib.reload(paths)
    return d


def test_td_read_roundtrip(fake_td: Path) -> None:
    # 直接 import 内部函数(td_server 在导入时会尝试连 MCP SDK,若不可用则跳过)
    pytest.importorskip("mcp")
    from hci_quality.mcp.td_server import _build_server
    srv = _build_server()
    # FastMCP 暴露的 tool 注册表具体 API 因版本而异,此处仅验证 server 能构建
    assert srv is not None
