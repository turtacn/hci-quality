# 07_run_eval.ps1
# 挖 golden TD + 跑 eval_join
$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root
& "$root\.venv\Scripts\Activate.ps1"

$repos = @("repos\perl-main","repos\go-main","repos\py-main","repos\java-main","repos\c-main") |
         Where-Object { Test-Path $_ }
if ($repos.Count -eq 0) {
  Write-Host "[FAIL] no repos present under repos/"
  exit 1
}
$reposArg = $repos -join ","

Write-Host "[1/2] mining golden TDs from: $reposArg"
python -m hci_quality.eval.golden_tds_mine --repos $reposArg --output configs\golden_tds.yaml

Write-Host "[2/2] running eval_join..."
$report = "logs\eval_baseline.json"
python -m hci_quality.eval.eval_join --golden configs\golden_tds.yaml --report $report
Get-Content $report

Write-Host ""
Write-Host "eval done. Report: $report"
