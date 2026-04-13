# 04_build_codegraph.ps1
# 对所有语言的源码工作树批量构建 Kuzu 调用图,再跑跨语言边界扫描
$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root
& "$root\.venv\Scripts\Activate.ps1"

$langs = @(
  @{ name = "perl";   path = "repos\perl-main" },
  @{ name = "go";     path = "repos\go-main" },
  @{ name = "python"; path = "repos\py-main" },
  @{ name = "java";   path = "repos\java-main" },
  @{ name = "c";      path = "repos\c-main" }
)

$first = $true
foreach ($l in $langs) {
  if (-not (Test-Path $l.path)) {
    Write-Host "[SKIP] $($l.name) repo not present at $($l.path)"
    continue
  }
  $flag = if ($first) { "" } else { "--incremental" }
  Write-Host "[build] lang=$($l.name) source=$($l.path) $flag"
  python -m hci_quality.graph.kuzu_build --source $l.path --language $l.name $flag
  $first = $false
}

Write-Host "[cross_boundary] scanning all repos..."
python -m hci_quality.graph.cross_boundary --all-repos --incremental

Write-Host "[dump] symbol registry snapshot..."
python -m hci_quality.lang_bridge.symbol_registry --dump configs\symbol_registry.yaml

Write-Host "codegraph build done."
