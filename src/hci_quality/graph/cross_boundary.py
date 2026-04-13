"""跨语言边界扫描器。

检测对象:
  - 共享 Unix Domain Socket 路径(Perl IO::Socket::UNIX / Go net.Listen unix / Python socket AF_UNIX / Java UnixDomainSocketAddress / C bind)
  - gRPC 服务名(proto 中的 service X)
  - FFI 符号(cgo #cgo / Python ctypes / Java JNI / Perl XS)
  - subprocess 命令名

产出:
  - Kuzu 中的 external_call 节点
  - binds_to 边(function -> external_call)
  - 若两侧都找到同一 external_entry,则建立 cross_calls 边
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import click

from ..lang_bridge.multi_lang_graph import MultiLangGraph
from ..utils.logging_setup import setup_logging
from ..utils.paths import KUZU_DIR, REPOS_DIR, ensure_dirs

log = logging.getLogger("hci_quality.graph.cross_boundary")

UDS_PATTERNS = {
    "perl":   re.compile(r"""IO::Socket::UNIX.*?Peer(?:Addr|Path)\s*=>\s*['"]([^'"]+\.sock)['"]""", re.S),
    "go":     re.compile(r'''net\.(?:Listen|Dial)\(\s*"unix"\s*,\s*"([^"]+\.sock)"'''),
    "python": re.compile(r'''socket\.AF_UNIX[^\n]*?\n[^\n]*?["\']([^"\']+\.sock)["\']''', re.S),
    "java":   re.compile(r'UnixDomainSocketAddress\.of\(\s*"([^"]+\.sock)"'),
    "c":      re.compile(r'sun_path\s*,\s*"([^"]+\.sock)"'),
}

GRPC_SERVICE = re.compile(r'^\s*service\s+(\w+)\s*\{', re.M)
CGO_IMPORT = re.compile(r'^\s*import\s+"C"', re.M)
JNI_SIG = re.compile(r'JNIEXPORT\s+\w+\s+JNICALL\s+(Java_[\w_]+)')
CTYPES_LOAD = re.compile(r'ctypes\.CDLL\(\s*["\']([^"\']+)["\']')


def scan_repo(lang: str, repo_root: Path) -> list[dict]:
    """返回 [{qname?, boundary_type, api_name, file}, ...]"""
    results: list[dict] = []
    if lang in UDS_PATTERNS:
        for ext in {"perl": "*.pm", "go": "*.go", "python": "*.py",
                    "java": "*.java", "c": "*.c"}[lang].split():
            for p in repo_root.rglob(ext):
                text = p.read_text(encoding="utf-8", errors="replace")
                for m in UDS_PATTERNS[lang].finditer(text):
                    results.append({
                        "boundary_type": "uds",
                        "api_name": m.group(1),
                        "file": str(p),
                    })

    # gRPC service 声明(只扫 .proto)
    for p in repo_root.rglob("*.proto"):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in GRPC_SERVICE.finditer(text):
            results.append({
                "boundary_type": "grpc",
                "api_name": m.group(1),
                "file": str(p),
            })

    # FFI
    if lang == "go":
        for p in repo_root.rglob("*.go"):
            if CGO_IMPORT.search(p.read_text(encoding="utf-8", errors="replace")):
                results.append({"boundary_type": "cgo", "api_name": p.stem, "file": str(p)})
    if lang == "java":
        for p in repo_root.rglob("*.c"):
            for m in JNI_SIG.finditer(p.read_text(encoding="utf-8", errors="replace")):
                results.append({"boundary_type": "jni", "api_name": m.group(1), "file": str(p)})
    if lang == "python":
        for p in repo_root.rglob("*.py"):
            for m in CTYPES_LOAD.finditer(p.read_text(encoding="utf-8", errors="replace")):
                results.append({"boundary_type": "ctypes", "api_name": m.group(1), "file": str(p)})

    return results


@click.command()
@click.option("--all-repos", is_flag=True, help="扫描 repos/ 下所有子目录")
@click.option("--repo", type=click.Path(path_type=Path), default=None)
@click.option("--incremental", is_flag=True)
def cli(all_repos: bool, repo: Path | None, incremental: bool) -> None:
    setup_logging("hci_quality.graph.cross_boundary")
    ensure_dirs()
    g = MultiLangGraph(str(KUZU_DIR))
    if not incremental:
        g.reset_schema()

    targets: list[tuple[str, Path]] = []
    if all_repos:
        mapping = {
            "perl-main": "perl", "go-main": "go", "py-main": "python",
            "java-main": "java", "c-main": "c",
        }
        for sub, lang in mapping.items():
            p = REPOS_DIR / sub
            if p.exists():
                targets.append((lang, p))
    elif repo:
        targets.append(("unknown", repo))

    total_edges = 0
    # 收集 uds/gRPC 字符串,用于两端 join
    by_api: dict[str, list[dict]] = {}
    for lang, root in targets:
        for item in scan_repo(lang, root):
            item["lang"] = lang
            by_api.setdefault(item["api_name"], []).append(item)
            g.upsert_external_call(
                lang=lang,
                api_name=item["api_name"],
                boundary_type=item["boundary_type"],
                description=item["file"],
            )

    # 凡是同一 api_name 在两种语言出现的,建 cross_calls
    for api, items in by_api.items():
        langs = {i["lang"] for i in items}
        if len(langs) >= 2:
            total_edges += g.link_cross_calls_by_api(api, items)

    log.info("CROSSES_BOUNDARY edges: %d", total_edges)
    print(f"CROSSES_BOUNDARY edges: {total_edges}")


if __name__ == "__main__":
    cli()
