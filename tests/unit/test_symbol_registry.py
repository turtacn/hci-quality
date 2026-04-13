"""Unit tests for lang_bridge.symbol_registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from hci_quality.lang_bridge.symbol_registry import (
    CParser,
    GoParser,
    JavaParser,
    PerlParser,
    PythonParser,
    SymbolRegistry,
)


def test_perl_canonical() -> None:
    assert PerlParser().normalize_name("Net::DHCP::renew") == "network.dhcp.renew"


def test_go_canonical() -> None:
    out = GoParser().normalize_name("github.com/hci/net.(*DHCP).Renew")
    assert "net" in out and "renew" in out


def test_python_canonical() -> None:
    assert PythonParser().normalize_name("net.dhcp.renew") == "network.dhcp.renew"


def test_java_canonical_strips_base_pkg() -> None:
    assert JavaParser().normalize_name("com.hci.network.DHCPService.renew") == "network.dhcpservice.renew"


def test_c_canonical_strips_prefix() -> None:
    assert CParser().normalize_name("dhcp.c::dhcp_renew") == "dhcp.renew"


def test_registry_roundtrip(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "sym.sqlite"
    reg = SymbolRegistry(db_path=db)
    reg.register("perl", "Net::DHCP::renew", "network.dhcp.renew",
                 file="Net/DHCP.pm", line_start=10)
    reg.register("go", "net.(*DHCP).Renew", "network.dhcp.renew",
                 file="net/dhcp.go", line_start=42)
    sym = reg.by_canonical("network.dhcp.renew")
    assert set(sym.variants) == {"perl", "go"}
    assert reg.lookup("perl", "Net::DHCP::renew").canonical_name == "network.dhcp.renew"
    pairs = reg.cross_lang_edges("perl", "go")
    assert ("Net::DHCP::renew", "net.(*DHCP).Renew", "network.dhcp.renew") in pairs
