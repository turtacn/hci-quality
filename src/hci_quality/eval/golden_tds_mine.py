"""从 git log 挖 golden TD 真值对。

算法:
  1. 扫描若干 repo 的 git log
  2. 匹配 commit message 中的 TD-\\d+ 正则(宽容大小写与前缀)
  3. 对匹配上的 commit:解析 diff 中被改动的文件与行号区间
  4. 用 tree-sitter 抽出行号区间落在哪个函数定义内,得到 qname 列表
  5. 经由 SymbolRegistry 归一为 canonical_name
  6. 产出 configs/golden_tds.yaml
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import click
import yaml

from ..lang_bridge.symbol_registry import SymbolRegistry
from ..utils.logging_setup import setup_logging
from ..utils.paths import CONFIGS_DIR

log = logging.getLogger("hci_quality.eval.golden_tds_mine")

TD_ID = re.compile(r"\bTD[-_ ]?(\d+)\b", re.I)


def _git_log(repo: Path, since: str = "1 year ago") -> list[dict]:
    """返回 [{sha, subject, body, files_changed}, ...]"""
    out = subprocess.run(
        ["git", "-C", str(repo), "log", f"--since={since}",
         "--pretty=format:%H%n%s%n%b%n==END=="],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    entries: list[dict] = []
    buf: list[str] = []
    for line in out.stdout.splitlines():
        if line == "==END==":
            if buf:
                sha = buf[0]
                subj = buf[1] if len(buf) > 1 else ""
                body = "\n".join(buf[2:]) if len(buf) > 2 else ""
                entries.append({"sha": sha, "subject": subj, "body": body, "repo": str(repo)})
                buf = []
        else:
            buf.append(line)
    return entries


def _diff_files(repo: Path, sha: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """返回 [(file, [(start, end), ...]), ...] 被改动的行号区间。"""
    out = subprocess.run(
        ["git", "-C", str(repo), "show", "--unified=0", "--format=", sha],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    files: list[tuple[str, list[tuple[int, int]]]] = []
    cur_file: str | None = None
    cur_hunks: list[tuple[int, int]] = []
    for line in out.stdout.splitlines():
        if line.startswith("+++ b/"):
            if cur_file:
                files.append((cur_file, cur_hunks))
            cur_file = line[6:]
            cur_hunks = []
        elif line.startswith("@@"):
            # @@ -a,b +c,d @@
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                start = int(m.group(1))
                length = int(m.group(2) or "1")
                cur_hunks.append((start, start + max(length - 1, 0)))
    if cur_file:
        files.append((cur_file, cur_hunks))
    return files


def _guess_lang(path: str) -> str | None:
    if path.endswith((".pm", ".pl")):
        return "perl"
    if path.endswith(".go"):
        return "go"
    if path.endswith(".py"):
        return "python"
    if path.endswith(".java"):
        return "java"
    if path.endswith((".c", ".h")):
        return "c"
    return None


def mine_for_repos(repos: Iterable[Path], since: str = "1 year ago") -> dict:
    reg = SymbolRegistry.load()
    result: dict[str, dict] = {}
    for repo in repos:
        if not (repo / ".git").exists() and not (repo / "HEAD").exists():
            log.warning("skip non-git path: %s", repo)
            continue
        for entry in _git_log(repo, since):
            text = f"{entry['subject']}\n{entry['body']}"
            for m in TD_ID.finditer(text):
                td_id = f"TD-{m.group(1)}"
                files = _diff_files(repo, entry["sha"])
                qnames: list[dict] = []
                for f, hunks in files:
                    lang = _guess_lang(f)
                    if not lang:
                        continue
                    # 粗略策略:不实际打开文件,仅记录 file+hunks,由后续 enrichment 脚本
                    # 通过 tree-sitter 转为精确 qname。第一版先标占位,避免重 IO。
                    for s, e in hunks:
                        qnames.append({
                            "lang": lang,
                            "file": f,
                            "line_start": s,
                            "line_end": e,
                            "qname": None,  # 待 enrichment
                        })
                if not qnames:
                    continue
                canonical = None
                # 简化:取第一个有已登记 canonical 的
                for q in qnames:
                    if q["qname"]:
                        sym = reg.lookup(q["lang"], q["qname"])
                        if sym:
                            canonical = sym.canonical_name
                            break

                result[td_id] = {
                    "canonical": canonical,
                    "qnames": qnames,
                    "commit": entry["sha"],
                    "mined_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
    return result


@click.command()
@click.option("--repos", required=True, help="逗号分隔的 repo 路径列表")
@click.option("--since", default="1 year ago", show_default=True)
@click.option("--output", type=click.Path(path_type=Path),
              default=CONFIGS_DIR / "golden_tds.yaml", show_default=True)
def cli(repos: str, since: str, output: Path) -> None:
    setup_logging("hci_quality.eval.golden_tds_mine")
    repo_paths = [Path(p.strip()) for p in repos.split(",") if p.strip()]
    data = mine_for_repos(repo_paths, since=since)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(data, allow_unicode=True, default_flow_style=False),
                      encoding="utf-8")
    log.info("mined %d golden TDs -> %s", len(data), output)
    print(f"mined {len(data)} golden TDs -> {output}")


if __name__ == "__main__":
    cli()
