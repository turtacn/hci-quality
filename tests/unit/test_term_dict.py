"""Unit tests for ingest.term_dict."""
from __future__ import annotations

from pathlib import Path

from hci_quality.ingest.term_dict import TermDict, Term, load_from


def test_match_longest_alias_first(tmp_path: Path) -> None:
    yaml_path = tmp_path / "terms.yaml"
    yaml_path.write_text(
        "- canonical: ha_agent_down\n"
        "  aliases: [HA, HA agent down]\n"
        "  owner_module: HCI-VCLS\n",
        encoding="utf-8",
    )
    td = load_from(yaml_path)
    hits = td.match("observed HA agent down event")
    assert any(t.canonical == "ha_agent_down" for t in hits)


def test_owner_lookup() -> None:
    td = TermDict([Term(canonical="x", aliases=["alpha"], owner_module="HCI-Mgmt")])
    assert td.owner_of("x") == "HCI-Mgmt"
    assert td.owner_of("missing") == "Unknown"


def test_empty_match() -> None:
    td = TermDict([])
    assert td.match("anything") == []
