"""TD 评论回写。

由 docs subagent 最后调用(或由 Claude CLI 子进程在收尾阶段调用)。
不把这一步放在 webhook 接收器内,避免接收器同步等待。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger("hci_quality.webhook.comment_writeback")

_TD_API_BASE = os.getenv("TD_API_BASE", "")
_TD_API_TOKEN = os.getenv("TD_API_TOKEN", "")


def writeback(td_id: str, comment_body: str, *,
              dry_run: bool = False, timeout: float = 10.0) -> dict:
    """把 comment_body 回写到 TD 评论区。

    失败时不抛异常,返回结构化 result,调用方自行判断。
    """
    result = {"td_id": td_id, "ok": False, "status_code": None, "error": None}

    if dry_run or not _TD_API_BASE:
        p = Path(f"logs/comment_writeback_{td_id}.md")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(comment_body, encoding="utf-8")
        result.update(ok=True, status_code=0, error="dry-run or TD_API_BASE unset")
        log.info("dry-run writeback saved to %s", p)
        return result

    url = f"{_TD_API_BASE.rstrip('/')}/td/{td_id}/comments"
    headers = {
        "Authorization": f"Bearer {_TD_API_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(url, headers=headers, json={"body": comment_body}, timeout=timeout)
        result["status_code"] = r.status_code
        result["ok"] = r.is_success
        if not r.is_success:
            result["error"] = r.text[:500]
    except httpx.HTTPError as e:
        result["error"] = str(e)
    log.info("writeback td_id=%s ok=%s code=%s", td_id, result["ok"], result["status_code"])
    return result
