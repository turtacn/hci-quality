# 02_verify_env.ps1
# 工具链版本校验
$ErrorActionPreference = "Continue"

function Test-Tool($name, $cmd, $expectPattern) {
  try {
    $out = & pwsh -NoProfile -Command $cmd 2>&1 | Out-String
    if ($out -match $expectPattern) {
      Write-Host "[OK]   $name -> $($out.Trim())"
      return $true
    } else {
      Write-Host "[FAIL] $name unexpected output: $($out.Trim())"
      return $false
    }
  } catch {
    Write-Host "[FAIL] $name not found"
    return $false
  }
}

$results = @()
$results += Test-Tool "pwsh"   "`$PSVersionTable.PSVersion.ToString()" "^7\."
$results += Test-Tool "python" "python --version" "^Python 3\.13"
$results += Test-Tool "node"   "node --version" "^v22\."
$results += Test-Tool "npm"    "npm --version" "^10\."
$results += Test-Tool "git"    "git --version" "^git version"
$results += Test-Tool "poetry" "poetry --version" "^Poetry"
$results += Test-Tool "uv"     "uv --version" "^uv "
$results += Test-Tool "dotnet" "dotnet --version" "^8\."

$ok  = ($results | Where-Object { $_ -eq $true }).Count
$bad = ($results | Where-Object { $_ -eq $false }).Count
Write-Host ""
Write-Host "Summary: $ok passed, $bad failed"
if ($bad -gt 0) { exit 1 }
