"""TD 归一化入口。

批量把 TD/iCare 原始 JSONL 转成 data/td/normalized/TD-*.json,字段包括:
  td_id, title, description, comments, severity, module,
  stack_qnames, error_codes, canonical_terms

支持 --push-lightrag 将同一批数据推送到 LightRAG。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

import click

from ..utils.logging_setup import setup_logging
from ..utils.paths import TD_NORMALIZED_DIR, TD_RAW_DIR, ensure_dirs
from .stack_extract import extract_error_codes, extract_qnames
from .term_dict import load_default

log = logging.getLogger("hci_quality.ingest")


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                log.warning("skip malformed line %d in %s", i, path)


def normalize_one(raw: dict) -> dict:
    """字段标准化。注意:各 TD 系统导出的字段名可能不同,这里做容错映射。"""
    td_id = str(raw.get("td_id") or raw.get("id") or raw.get("number") or "").strip()
    if not td_id:
        raise KeyError("td_id missing; please adjust field mapping in td_normalize.normalize_one")

    text_all = "\n".join(filter(None, [
        str(raw.get("title", "")),
        str(raw.get("description", "")),
        str(raw.get("comments", "")),
    ]))

    terms = load_default().match(text_all)
    canonical_terms = [t.canonical for t in terms]
    owner_module = terms[0].owner_module if terms else str(raw.get("module", "Unknown"))

    return {
        "td_id": td_id,
        "title": str(raw.get("title", "")),
        "description": str(raw.get("description", "")),
        "comments": str(raw.get("comments", "")),
        "severity": str(raw.get("severity", "P3")),
        "module": owner_module,
        "stack_qnames": extract_qnames(text_all),
        "error_codes": extract_error_codes(text_all),
        "canonical_terms": canonical_terms,
    }


def write_one(td: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{td['td_id']}.json"
    p.write_text(json.dumps(td, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def run_normalize(input_path: Path, output_dir: Path, limit: int | None = None) -> int:
    count = 0
    for raw in _iter_jsonl(input_path):
        try:
            td = normalize_one(raw)
        except KeyError as e:
            log.error("%s", e)
            continue
        write_one(td, output_dir)
        count += 1
        if limit and count >= limit:
            break
    log.info("normalized %d TDs -> %s", count, output_dir)
    return count


def run_push_lightrag(output_dir: Path, limit: int | None = None) -> int:
    from .lightrag_adapter import upsert
    docs = []
    for i, p in enumerate(sorted(output_dir.glob("*.json"))):
        if limit and i >= limit:
            break
        docs.append(json.loads(p.read_text(encoding="utf-8")))
    n = upsert(docs)
    log.info("LightRAG upsert done: %d docs", n)
    return n


@click.command()
@click.option("--input", "input_path", type=click.Path(path_type=Path),
              default=TD_RAW_DIR / "td_last_3month.jsonl", show_default=True)
@click.option("--output", "output_dir", type=click.Path(path_type=Path),
              default=TD_NORMALIZED_DIR, show_default=True)
@click.option("--limit", type=int, default=None)
@click.option("--push-lightrag", is_flag=True, help="Push normalized TDs into LightRAG")
def cli(input_path: Path, output_dir: Path, limit: int | None, push_lightrag: bool) -> None:
    setup_logging("hci_quality.ingest")
    ensure_dirs()
    if push_lightrag:
        run_push_lightrag(output_dir, limit)
    else:
        run_normalize(input_path, output_dir, limit)


if __name__ == "__main__":
    cli()
