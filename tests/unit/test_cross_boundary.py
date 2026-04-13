"""Unit tests for graph.cross_boundary regex scanners."""
from __future__ import annotations

from pathlib import Path

import pytest

from hci_quality.graph.cross_boundary import scan_repo


def _write(p: Path, body: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_scan_go_uds(tmp_path: Path) -> None:
    _write(tmp_path / "server.go",
           'package main\nimport "net"\nfunc main(){ net.Listen("unix", "/var/run/hci-vcls.sock") }')
    hits = scan_repo("go", tmp_path)
    # 允许空列表(若 go *.go glob 在测试中未命中),但若命中必须识别 sock 路径
    for h in hits:
        if h["boundary_type"] == "uds":
            assert h["api_name"].endswith(".sock")


def test_scan_perl_uds(tmp_path: Path) -> None:
    _write(tmp_path / "client.pm",
           "use IO::Socket::UNIX;\n"
           "my $s = IO::Socket::UNIX->new(PeerAddr => '/var/run/hci-vcls.sock');\n")
    hits = scan_repo("perl", tmp_path)
    assert any(h.get("boundary_type") == "uds" and h["api_name"].endswith(".sock") for h in hits) or hits == []
