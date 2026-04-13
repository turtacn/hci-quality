# 99_e2e_smoke.ps1
# 端到端冒烟:按 docs/mvp-bootstrap.md 的验收判据逐一回归,输出 pass/fail 矩阵
$ErrorActionPreference = "Continue"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root

$results = @()

function Check($id, $block) {
  try {
    $extra = & $block 2>&1 | Out-String
    $extra = $extra.Trim()
    if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
      "[$id] PASS" + $(if ($extra) { " ($extra)" } else { "" }) | Write-Host
      return $true
    } else {
      "[$id] FAIL ($extra)" | Write-Host
      return $false
    }
  } catch {
    "[$id] FAIL ($($_.Exception.Message))" | Write-Host
    return $false
  }
}

# --- Phase 1 ---
$results += Check "Action-1.2" { pwsh -NoProfile -Command "python --version" | Out-Null }
$results += Check "Action-1.3" { if (Test-Path "$root\.venv\Scripts\python.exe") { "venv ok" } else { throw "venv missing" } }
$results += Check "Action-1.4" {
  & "$root\.venv\Scripts\Activate.ps1"
  python -c "import lightrag, kuzu, phoenix, fastapi, mcp" | Out-Null
}
$results += Check "Action-1.5" { claude --version | Out-Null }
$results += Check "Action-1.7" {
  & "$root\.venv\Scripts\Activate.ps1"
  $env:TRANSFORMERS_OFFLINE = "1"
  $env:HF_HUB_OFFLINE = "1"
  python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer(r'$root\models\bge-m3', device='cpu'); print('embed_dim=', m.get_sentence_embedding_dimension())"
}
$results += Check "Action-1.8" {
  if ((Get-ChildItem "$root\data\td\normalized" -Filter "TD-*.json" -ErrorAction SilentlyContinue).Count -gt 0) { "normalized ok" } else { throw "no normalized TD" }
}

# --- Phase 2 ---
$results += Check "Action-2.2" {
  if (Test-Path "$root\data\codegraph.kuzu") { "kuzu dir ok" } else { throw "kuzu dir missing" }
}
$results += Check "Action-2.3" {
  & "$root\.venv\Scripts\Activate.ps1"
  python -c "from hci_quality.graph.kuzu_build import query; r = query('MATCH (f:function) RETURN count(f) AS n'); print('functions=', r)"
}
$results += Check "Action-2.4" {
  if (Test-Path "$root\.mcp.json") { ".mcp.json present" } else { throw ".mcp.json missing" }
}

# --- Phase 3 ---
$results += Check "Action-3.1" {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:6006" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { "phoenix up" } else { throw "status $($r.StatusCode)" }
  } catch { throw "Phoenix not reachable at :6006" }
}
$results += Check "Action-3.3" {
  if (Test-Path "$root\logs\eval_baseline.json") { "baseline exists" } else { throw "no eval baseline" }
}
$results += Check "Action-3.4" {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:8088/healthz" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { "webhook up" } else { throw "status $($r.StatusCode)" }
  } catch { throw "Webhook not reachable at :8088" }
}

$ok = ($results | Where-Object { $_ -eq $true }).Count
$bad = ($results | Where-Object { $_ -eq $false }).Count
Write-Host ""
Write-Host "Summary: $ok passed, $bad failed"
if ($bad -gt 0) { exit 1 }
