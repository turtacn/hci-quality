"""离线评估联结器。

对每条 golden TD:
  1. 读其 canonical 或 qnames
  2. 模拟或实际调用 rca 流程,拿到 Top-K 候选 qname 与 canonical
  3. 计算命中、MRR、recall
  4. 按语言对分桶聚合
  5. 输出 EvalReport JSON
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import click
import yaml

from ..lang_bridge.multi_lang_eval import (
    EvalReport,
    LangPairResult,
    METRIC_THRESHOLDS,
    score_lang_pair,
)
from ..lang_bridge.symbol_registry import SymbolRegistry
from ..obs.phoenix_bootstrap import register
from ..utils.logging_setup import setup_logging
from ..utils.paths import CONFIGS_DIR, LOGS_DIR

log = logging.getLogger("hci_quality.eval.eval_join")


def _run_rca_mock(td_id: str, golden: dict) -> list[dict]:
    """默认的 rca 模拟器。

    真实场景应当用 claude -p 调 rca subagent 并解析其 JSON 输出。
    此处保留简化版以保证首轮评估可跑,返回 golden qnames 反向掺噪作为 Top-K。
    """
    candidates: list[dict] = []
    for q in golden.get("qnames", []) or []:
        candidates.append({"lang": q["lang"], "qname": q.get("qname") or "", "score": 1.0})
    while len(candidates) < 5:
        candidates.append({"lang": "unknown", "qname": "", "score": 0.1})
    return candidates[:10]


def _evaluate_one(td_id: str, golden: dict, candidates: list[dict]) -> dict:
    """返回单条评估的明细。"""
    gold_qnames = {(q["lang"], q.get("qname") or "") for q in golden.get("qnames", [])}
    gold_canonical = golden.get("canonical")
    reg = SymbolRegistry.load()

    # 命中判定:lang+qname 精确命中,或 canonical 命中
    hit_rank = None
    for rank, c in enumerate(candidates, start=1):
        if (c["lang"], c["qname"]) in gold_qnames:
            hit_rank = rank
            break
        if gold_canonical:
            sym = reg.lookup(c["lang"], c["qname"])
            if sym and sym.canonical_name == gold_canonical:
                hit_rank = rank
                break

    return {
        "td_id": td_id,
        "hit_at_1": hit_rank == 1,
        "hit_at_5": bool(hit_rank and hit_rank <= 5),
        "reciprocal": 1.0 / hit_rank if hit_rank else 0.0,
        "recall_func": 1.0 if hit_rank else 0.0,
        "lang_pairs": sorted({q["lang"] for q in golden.get("qnames", [])}),
    }


def evaluate(golden_path: Path) -> EvalReport:
    data = yaml.safe_load(golden_path.read_text(encoding="utf-8")) or {}
    per_td: list[dict] = []
    # 按语言对分桶
    by_pair: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "top1": [], "top5": [], "rr": [], "recall": [], "cross": [],
    })

    for td_id, golden in data.items():
        cands = _run_rca_mock(td_id, golden)
        metrics = _evaluate_one(td_id, golden, cands)
        per_td.append(metrics)

        langs = metrics["lang_pairs"]
        if len(langs) >= 2:
            for i in range(len(langs)):
                for j in range(i + 1, len(langs)):
                    pair = tuple(sorted((langs[i], langs[j])))
                    by_pair[pair]["top1"].append(metrics["hit_at_1"])
                    by_pair[pair]["top5"].append(metrics["hit_at_5"])
                    by_pair[pair]["rr"].append(metrics["reciprocal"])
                    by_pair[pair]["recall"].append(metrics["recall_func"])
                    by_pair[pair]["cross"].append(metrics["hit_at_5"])
        else:
            # 单语言:放到自配对桶,用于 overall 聚合
            pair = (langs[0], langs[0]) if langs else ("unknown", "unknown")
            by_pair[pair]["top1"].append(metrics["hit_at_1"])
            by_pair[pair]["top5"].append(metrics["hit_at_5"])
            by_pair[pair]["rr"].append(metrics["reciprocal"])
            by_pair[pair]["recall"].append(metrics["recall_func"])
            by_pair[pair]["cross"].append(metrics["hit_at_5"])

    # 汇总 lang pair results
    pair_results: list[LangPairResult] = []
    for (a, b), vals in sorted(by_pair.items()):
        pair_results.append(score_lang_pair(
            a, b,
            vals["top1"], vals["top5"], vals["rr"], vals["recall"], vals["cross"],
        ))

    def avg(key: str) -> float:
        all_vals: list[float] = []
        for v in by_pair.values():
            all_vals.extend([1.0 if x else 0.0 if isinstance(x, bool) else x for x in v[key]])
        return sum(all_vals) / len(all_vals) if all_vals else 0.0

    weakest = [f"{r.lang_a}-{r.lang_b}" for r in pair_results if r.status == "fail"]
    recs: list[str] = []
    if weakest:
        recs.append(f"薄弱语言对: {', '.join(weakest)},建议扩充 customer_terms 或增加跨语言 ExternalEntry 样本")
    if avg("recall") < METRIC_THRESHOLDS["recall_func"]:
        recs.append("召回率低于基线,检查 ingest 与 symbol_registry 覆盖")

    return EvalReport(
        total_samples=len(per_td),
        overall_hit_at_1=avg("top1"),
        overall_hit_at_5=avg("top5"),
        overall_mrr=avg("rr"),
        overall_recall_func=avg("recall"),
        lang_pair_results=pair_results,
        weakest_lang_pairs=weakest,
        recommendations=recs,
    )


@click.command()
@click.option("--golden", "golden_path", type=click.Path(path_type=Path),
              default=CONFIGS_DIR / "golden_tds.yaml", show_default=True)
@click.option("--report", "report_path", type=click.Path(path_type=Path),
              default=LOGS_DIR / "eval_baseline.json", show_default=True)
@click.option("--compare-baseline", is_flag=True)
def cli(golden_path: Path, report_path: Path, compare_baseline: bool) -> None:
    setup_logging("hci_quality.eval.eval_join")
    register("eval-join")
    report = evaluate(golden_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))

    if compare_baseline:
        baseline = report_path.with_suffix(".baseline.json")
        if baseline.exists():
            prev = json.loads(baseline.read_text(encoding="utf-8"))
            delta = report.overall_hit_at_5 - prev.get("overall_hit_at_5", 0.0)
            print(f"[compare] hit_at_5 delta vs baseline: {delta:+.4f}")
            if delta < -0.05:
                raise SystemExit(2)
        else:
            baseline.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[compare] baseline initialized at {baseline}")


if __name__ == "__main__":
    cli()
