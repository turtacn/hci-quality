"""TD webhook FastAPI 接收器。

职责(约 120 行):
  - POST /td/webhook 接 TD 新单事件
  - 校验 schema 落盘 data/td/tasks/
  - subprocess.Popen 启动 `claude -p` 子进程
  - 立即返回 202 accepted 或 208 already_reported
  - GET /healthz 存活探测
  - 并发由 asyncio.Semaphore 受 HCIQ_MAX_PARALLEL 约束
  - 去重由 (td_id, 10 分钟窗口) 内存字典实现
"""
from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

from ..obs.phoenix_bootstrap import register
from ..utils.logging_setup import setup_logging
from ..utils.paths import REPOS_DIR, TD_TASKS_DIR, ensure_dirs

log = setup_logging("hci_quality.webhook")
register("webhook")

MAX_PARALLEL = int(os.getenv("HCIQ_MAX_PARALLEL", "3"))
DEDUP_WINDOW_SEC = 600
_SEM = asyncio.Semaphore(MAX_PARALLEL)
_RECENT: dict[str, float] = {}  # td_id -> last_accept_ts
_CHILDREN: list[subprocess.Popen] = []


class TDPayload(BaseModel):
    td_id: str = Field(..., min_length=1, max_length=64)
    title: str = Field("", max_length=400)
    description: str = Field("", max_length=20000)
    severity: Optional[str] = None
    module: Optional[str] = None


app = FastAPI(title="hci-quality TD webhook")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "active": len(_CHILDREN), "max_parallel": MAX_PARALLEL}


def _is_duplicate(td_id: str) -> bool:
    now = time.time()
    for k, ts in list(_RECENT.items()):
        if now - ts > DEDUP_WINDOW_SEC:
            del _RECENT[k]
    return td_id in _RECENT


def _record(td_id: str) -> None:
    _RECENT[td_id] = time.time()


def _pick_workdir(module: Optional[str]) -> Path:
    """根据 module 名选择一个源码 worktree 作为 --cwd。找不到就退回 repos/demo。"""
    if module:
        stem = module.lower().replace("-", "").replace(" ", "")
        for p in REPOS_DIR.iterdir() if REPOS_DIR.exists() else []:
            if p.is_dir() and stem in p.name.lower():
                return p
    demo = REPOS_DIR / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    return demo


def _spawn(td: TDPayload, task_file: Path) -> Optional[subprocess.Popen]:
    prompt = (
        f"分析 {td.td_id}:{td.title}\n\n"
        f"描述:{td.description}\n\n"
        f"请按 .claude/agents/ 中的 triage → rca → patch → regression → security → docs "
        f"流水线处理,最后按 docs subagent 的模板产出评论回写。"
    )
    workdir = _pick_workdir(td.module)
    cmd = [
        "claude", "-p", prompt,
        "--cwd", str(workdir),
        "--output-format", "json",
    ]
    log.info("spawn claude -p cwd=%s task=%s", workdir, task_file.name)
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdout=open(task_file.with_suffix(".stdout.log"), "w", encoding="utf-8"),
            stderr=open(task_file.with_suffix(".stderr.log"), "w", encoding="utf-8"),
        )
        _CHILDREN.append(proc)
        return proc
    except FileNotFoundError:
        log.error("claude CLI not found; ensure npm install -g @anthropic-ai/claude-code")
        return None


@app.post("/td/webhook")
async def on_td_event(payload: TDPayload, request: Request, response: Response) -> dict:
    ensure_dirs()
    if _is_duplicate(payload.td_id):
        response.status_code = 208
        return {"status": "already_reported", "td_id": payload.td_id}

    _record(payload.td_id)
    task_file = TD_TASKS_DIR / f"{payload.td_id}-{uuid.uuid4().hex[:6]}.txt"
    task_file.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    log.info("accepted td_id=%s task=%s", payload.td_id, task_file.name)

    # 并发受 semaphore 限制;超额排队
    async def _run():
        async with _SEM:
            proc = await asyncio.get_running_loop().run_in_executor(None, _spawn, payload, task_file)
            if proc is None:
                return
            # 轮询等待,不阻塞 event loop
            while proc.poll() is None:
                await asyncio.sleep(2)
            if proc in _CHILDREN:
                _CHILDREN.remove(proc)
            log.info("claude subprocess finished td_id=%s rc=%s", payload.td_id, proc.returncode)

    asyncio.get_running_loop().create_task(_run())
    response.status_code = 202
    return {"status": "accepted", "td_id": payload.td_id, "task_file": task_file.name}
