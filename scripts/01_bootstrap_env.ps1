# 01_bootstrap_env.ps1
# 创建 Python 虚拟环境并安装 hci-quality 依赖(走内网 PyPI 镜像)
$ErrorActionPreference = "Stop"
$root = "D:\opt-hci-quality\mvp"
Set-Location $root

if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
  Write-Host "[1/3] Creating venv..."
  python -m venv .venv
}

Write-Host "[2/3] Activating venv and upgrading pip..."
& "$root\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip

Write-Host "[3/3] Installing hci-quality (editable, dev extras) from internal PyPI mirror..."
pip install -e ".[dev]"

Write-Host ""
python -c "import lightrag, kuzu, phoenix, fastapi, tree_sitter_languages, drain3, sentence_transformers, mcp; print('[OK] all imports succeed')"
Write-Host "bootstrap_env done."
