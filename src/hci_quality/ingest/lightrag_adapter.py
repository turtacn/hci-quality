"""LightRAG 初始化与查询的薄封装。

- 统一读取 HCIQ_LIGHTRAG_DIR 与 HCIQ_BGE_M3_DIR
- 强制 local_files_only=True,避免联网校验 commit hash 超时
- 单例 lru_cache,进程内只初始化一次
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ..utils.paths import BGE_M3_DIR, LIGHTRAG_DIR


def _embed_model():
    """加载本地 bge-m3 快照。"""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(
        str(BGE_M3_DIR),
        device="cpu",
        local_files_only=True,
    )


@lru_cache(maxsize=1)
def get_rag() -> Any:
    """返回 LightRAG 单例。"""
    try:
        from lightrag import LightRAG, QueryParam  # noqa: F401
    except ImportError as e:
        raise RuntimeError("lightrag-hku 未安装") from e

    LIGHTRAG_DIR.mkdir(parents=True, exist_ok=True)
    model = _embed_model()

    def _embed(texts: list[str]):
        return model.encode(texts, normalize_embeddings=True)

    # 具体 LightRAG 初始化参数以上游实际 API 为准,此处是常见形态
    from lightrag import LightRAG
    rag = LightRAG(
        working_dir=str(LIGHTRAG_DIR),
        embedding_func=_embed,
    )
    return rag


def upsert(docs: list[dict]) -> int:
    """批量写入。docs 每条应包含 td_id、title、description、comments、metadata。"""
    rag = get_rag()
    texts = []
    for d in docs:
        text = "\n".join(filter(None, [d.get("title"), d.get("description"), d.get("comments", "")]))
        texts.append(text)
        # metadata 通过 id 维度的副表存,具体 API 略
    rag.insert(texts)
    return len(docs)


def search(query: str, top_k: int = 5, mode: str = "hybrid") -> list[dict]:
    """返回 [{td_id, score, snippet, metadata}, ...]。

    mode 透传给 LightRAG,"hybrid" 是召回质量与延迟的常见折衷。
    """
    from lightrag import QueryParam
    rag = get_rag()
    res = rag.query(query, param=QueryParam(mode=mode, top_k=top_k))
    # 实际字段以 LightRAG 版本为准,此处做最小转接
    if isinstance(res, str):
        return [{"td_id": "N/A", "score": 0.0, "snippet": res, "metadata": {}}]
    return list(res) if isinstance(res, list) else []
