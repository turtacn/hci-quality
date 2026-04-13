# 05_start_phoenix.ps1
# 前台启动 Phoenix 观测后端
$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root
& "$root\.venv\Scripts\Activate.ps1"

$env:PHOENIX_WORKING_DIR = "$root\traces"
if ($env:PHOENIX_PORT) {
  Write-Host "Starting Phoenix on port $($env:PHOENIX_PORT)"
} else {
  Write-Host "Starting Phoenix on default port 6006"
}
Write-Host "WORKING_DIR = $($env:PHOENIX_WORKING_DIR)"
Write-Host "Press Ctrl+C to stop."
python -m phoenix.server.main serve
