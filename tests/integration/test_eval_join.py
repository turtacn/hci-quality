"""Integration test: eval_join on a tiny synthetic golden set."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from hci_quality.eval.eval_join import evaluate


def test_eval_join_minimal(tmp_path: Path) -> None:
    golden = {
        "TD-1": {
            "canonical": "network.dhcp.renew",
            "qnames": [
                {"lang": "perl", "qname": "Net::DHCP::renew", "file": "Net/DHCP.pm",
                 "line_start": 1, "line_end": 2},
                {"lang": "go", "qname": "net.(*DHCP).Renew", "file": "net/dhcp.go",
                 "line_start": 3, "line_end": 4},
            ],
            "commit": "deadbeef",
            "mined_at": "2026-01-01T00:00:00+00:00",
        }
    }
    golden_path = tmp_path / "golden_tds.yaml"
    golden_path.write_text(yaml.safe_dump(golden, allow_unicode=True), encoding="utf-8")

    report = evaluate(golden_path)
    assert report.total_samples == 1
    assert 0.0 <= report.overall_hit_at_5 <= 1.0
    assert any(r.lang_a == "go" and r.lang_b == "perl" or r.lang_b == "go" and r.lang_a == "perl"
               for r in report.lang_pair_results)
