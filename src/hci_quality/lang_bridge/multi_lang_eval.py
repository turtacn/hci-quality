"""多语言评估的指标定义与加权聚合。

阈值见 ADR-0006。eval_join.py 会在运行时消费本模块的 METRIC_THRESHOLDS 与
LangPairResult。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

# ADR-0006 表列
METRIC_THRESHOLDS: dict[str, float] = {
    "hit_at_5_perl_python": 0.50,
    "hit_at_5_perl_java":   0.50,
    "hit_at_5_perl_go":     0.55,
    "hit_at_5_perl_c":      0.40,
    "hit_at_5_python_java": 0.50,
    "hit_at_5_python_go":   0.50,
    "hit_at_5_python_c":    0.40,
    "hit_at_5_go_java":     0.50,
    "hit_at_5_go_c":        0.40,
    "hit_at_5_java_c":      0.40,
    "mrr_weighted":         0.40,
    "recall_func":          0.45,
    "cross_lang_perl_go":   0.70,
    "cross_lang_perl_py":   0.60,
    "cross_lang_py_go":     0.55,
    "cross_lang_py_java":   0.50,
    "cross_lang_go_c":      0.45,
}


@dataclass
class LangPairResult:
    lang_a: str
    lang_b: str
    hit_at_5: float
    mrr: float
    recall_func: float
    cross_lang_acc: float
    sample_count: int
    status: str  # pass / warn / fail


@dataclass
class EvalReport:
    total_samples: int
    overall_hit_at_1: float
    overall_hit_at_5: float
    overall_mrr: float
    overall_recall_func: float
    lang_pair_results: list[LangPairResult] = field(default_factory=list)
    weakest_lang_pairs: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_samples": self.total_samples,
            "overall_hit_at_1": round(self.overall_hit_at_1, 4),
            "overall_hit_at_5": round(self.overall_hit_at_5, 4),
            "overall_mrr": round(self.overall_mrr, 4),
            "overall_recall_func": round(self.overall_recall_func, 4),
            "lang_pair_results": [asdict(r) for r in self.lang_pair_results],
            "weakest_lang_pairs": self.weakest_lang_pairs,
            "recommendations": self.recommendations,
        }


def score_lang_pair(a: str, b: str, hits_top1: Iterable[bool],
                    hits_top5: Iterable[bool], reciprocals: Iterable[float],
                    recalls: Iterable[float], cross_hits: Iterable[bool]) -> LangPairResult:
    hits_top1 = list(hits_top1)
    hits_top5 = list(hits_top5)
    reciprocals = list(reciprocals)
    recalls = list(recalls)
    cross_hits = list(cross_hits)
    n = max(len(hits_top5), 1)

    def avg(xs: list[float]) -> float:
        return sum(xs) / n if n else 0.0

    hit5 = avg([1.0 if h else 0.0 for h in hits_top5])
    mrr = avg(reciprocals)
    recall = avg(recalls)
    cross_acc = avg([1.0 if h else 0.0 for h in cross_hits])

    threshold_key = f"hit_at_5_{a}_{b}"
    threshold = METRIC_THRESHOLDS.get(threshold_key, 0.40)
    if hit5 >= threshold:
        status = "pass"
    elif hit5 >= threshold * 0.85:
        status = "warn"
    else:
        status = "fail"

    return LangPairResult(
        lang_a=a,
        lang_b=b,
        hit_at_5=round(hit5, 4),
        mrr=round(mrr, 4),
        recall_func=round(recall, 4),
        cross_lang_acc=round(cross_acc, 4),
        sample_count=n,
        status=status,
    )
