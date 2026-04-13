# 06_start_webhook.ps1
# 前台启动 FastAPI TD webhook 接收器
$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root
& "$root\.venv\Scripts\Activate.ps1"

if (-not $env:HCIQ_MAX_PARALLEL) { $env:HCIQ_MAX_PARALLEL = "3" }
if (-not $env:OTEL_EXPORTER_OTLP_ENDPOINT) {
  $env:OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:6006/v1/traces"
}

$port = if ($env:HCIQ_WEBHOOK_PORT) { $env:HCIQ_WEBHOOK_PORT } else { "8088" }
Write-Host "Starting webhook on 0.0.0.0:$port (max_parallel=$($env:HCIQ_MAX_PARALLEL))"
uvicorn hci_quality.webhook.td_listener:app --host 0.0.0.0 --port $port --log-level info
