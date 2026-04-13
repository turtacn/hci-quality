# 03_ingest_td.ps1
# 导入 TD 历史数据并灌入 LightRAG
$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root
& "$root\.venv\Scripts\Activate.ps1"

$env:TRANSFORMERS_OFFLINE = "1"
$env:HF_HUB_OFFLINE = "1"

$raw = "data\td\raw\td_last_3month.jsonl"
if (-not (Test-Path $raw)) {
  Write-Host "[FAIL] raw TD not found: $raw"
  Write-Host "       请先把 TD 导出 JSONL 放到 $raw"
  exit 1
}

$limit = if ($env:HCIQ_INGEST_LIMIT) { $env:HCIQ_INGEST_LIMIT } else { "200" }

Write-Host "[1/2] normalize TD from $raw (limit=$limit)..."
python -m hci_quality.ingest.td_normalize --input $raw --output data\td\normalized --limit $limit

Write-Host "[2/2] push to LightRAG (limit=$limit)..."
python -m hci_quality.ingest.td_normalize --push-lightrag --limit $limit

Write-Host "ingest done."
