# create_scaffold.ps1
# 按 README 目录与文件清单,在 D:\opt-hci-quality\mvp 一次性创建完整空骨架
# 幂等:已存在的目录或文件会被 New-Item -Force 处理为无操作

$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
New-Item -ItemType Directory -Force -Path $root | Out-Null
Set-Location $root

$dirs = @(
  "docs/adr","docs/diagrams",
  ".claude/agents",".claude/commands",
  "src/hci_quality/ingest","src/hci_quality/graph","src/hci_quality/lang_bridge",
  "src/hci_quality/mcp","src/hci_quality/webhook","src/hci_quality/eval",
  "src/hci_quality/obs","src/hci_quality/utils",
  "configs","scripts",
  "tests/unit","tests/integration",
  "data/td/raw","data/td/normalized","data/td/tasks","data/templates",
  "models","repos","logs","traces","mcp"
)
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
  Write-Host "[OK dir]  $d"
}

$files = @(
  "README.md","pyproject.toml",".mcp.json",".gitignore",".env.example","config.toml","LICENSE",
  "docs/architecture.md","docs/roadmap.md","docs/mvp-bootstrap.md","docs/operations.md","docs/references.md",
  "docs/adr/0001-no-docker-windows.md","docs/adr/0002-phoenix-over-langfuse.md",
  "docs/adr/0003-fastapi-over-open-swe.md","docs/adr/0004-claude-code-as-hands.md",
  "docs/adr/0005-internal-mirror-over-offline-wheel.md","docs/adr/0006-multi-language-symbol-registry.md",
  ".claude/agents/triage.md",".claude/agents/reproduce.md",".claude/agents/rca.md",
  ".claude/agents/patch.md",".claude/agents/regression.md",".claude/agents/security.md",".claude/agents/docs.md",
  ".claude/commands/mvp-bootstrap.md",".claude/commands/e2e-smoke.md",
  "src/hci_quality/__init__.py",
  "src/hci_quality/ingest/__init__.py","src/hci_quality/ingest/td_normalize.py",
  "src/hci_quality/ingest/term_dict.py","src/hci_quality/ingest/drain_parser.py",
  "src/hci_quality/ingest/stack_extract.py","src/hci_quality/ingest/lightrag_adapter.py",
  "src/hci_quality/graph/__init__.py","src/hci_quality/graph/tree_sitter_extract.py",
  "src/hci_quality/graph/kuzu_build.py","src/hci_quality/graph/cross_boundary.py",
  "src/hci_quality/lang_bridge/__init__.py","src/hci_quality/lang_bridge/symbol_registry.py",
  "src/hci_quality/lang_bridge/multi_lang_graph.py","src/hci_quality/lang_bridge/multi_lang_log_parser.py",
  "src/hci_quality/lang_bridge/multi_lang_eval.py",
  "src/hci_quality/mcp/__init__.py","src/hci_quality/mcp/_common.py",
  "src/hci_quality/mcp/lightrag_server.py","src/hci_quality/mcp/kuzu_server.py",
  "src/hci_quality/mcp/td_server.py",
  "src/hci_quality/webhook/__init__.py","src/hci_quality/webhook/td_listener.py",
  "src/hci_quality/webhook/comment_writeback.py",
  "src/hci_quality/eval/__init__.py","src/hci_quality/eval/golden_tds_mine.py",
  "src/hci_quality/eval/eval_join.py",
  "src/hci_quality/obs/__init__.py","src/hci_quality/obs/phoenix_bootstrap.py",
  "src/hci_quality/utils/__init__.py","src/hci_quality/utils/logging_setup.py","src/hci_quality/utils/paths.py",
  "configs/customer_terms.yaml","configs/golden_tds.yaml","configs/module_owners.yaml","configs/logging.yaml",
  "scripts/01_bootstrap_env.ps1","scripts/02_verify_env.ps1","scripts/03_ingest_td.ps1",
  "scripts/04_build_codegraph.ps1","scripts/05_start_phoenix.ps1","scripts/06_start_webhook.ps1",
  "scripts/07_run_eval.ps1","scripts/99_e2e_smoke.ps1","scripts/create_scaffold.ps1",
  "tests/__init__.py","tests/unit/__init__.py","tests/unit/test_term_dict.py",
  "tests/unit/test_symbol_registry.py","tests/unit/test_cross_boundary.py",
  "tests/integration/__init__.py","tests/integration/test_mcp_roundtrip.py",
  "tests/integration/test_eval_join.py"
)
foreach ($f in $files) {
  New-Item -ItemType File -Force -Path $f | Out-Null
  Write-Host "[OK file] $f"
}

Write-Host ""
Write-Host "Scaffold created at $root"
Write-Host "Directories: $($dirs.Count), Files: $($files.Count)"
