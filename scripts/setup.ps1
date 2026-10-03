# scripts/setup.ps1 —— 在 Windows PowerShell 5.1 上创建本地开发环境
#
# 行为（与 scripts/setup.sh 对齐）：
#   1. 检测 Python 版本（要求 >= 3.10）
#   2. 创建 .venv 虚拟环境（已存在则复用，脚本幂等）
#   3. 升级 pip / setuptools / wheel
#   4. 以可编辑模式安装项目及 dev 额外依赖（.[dev]）
#   5. 打印激活方式与常用命令
#
# 兼容性：仅使用 Windows PowerShell 5.1 支持的语法，
#         不使用 && / || / 三元 / ?? / ?. 等 PowerShell 7+ 特性。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
#   .\scripts\setup.ps1 -PythonExe python3.12
#   .\scripts\setup.ps1 -VenvDir .venv312

[CmdletBinding()]
param(
    [string]$PythonExe = "python",
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

# 中文输出统一使用 UTF-8，避免控制台乱码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 定位仓库根目录（本脚本位于 <root>/scripts 下）
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
Set-Location -LiteralPath $RootDir

$MinMajor = 3
$MinMinor = 10

# ---- 1. 检查解释器是否存在 -------------------------------------------------
$cmd = Get-Command $PythonExe -ErrorAction SilentlyContinue
if ($null -eq $cmd) {
    Write-Host "错误：未找到 Python 解释器 '$PythonExe'，请先安装 Python $MinMajor.$MinMinor+，或用 -PythonExe 指定路径。" -ForegroundColor Red
    exit 1
}

# ---- 检测版本 --------------------------------------------------------------
$versionOut = & $PythonExe -c "import sys; print('%d.%d.%d' % sys.version_info[:3])"
if (-not $?) {
    Write-Host "错误：无法执行 Python 解释器 '$PythonExe'。" -ForegroundColor Red
    exit 1
}
$versionOut = $versionOut.ToString().Trim()

$okOut = & $PythonExe -c "import sys; print(1 if sys.version_info >= ($MinMajor, $MinMinor) else 0)"
if (-not $?) {
    Write-Host "错误：Python 版本检测失败。" -ForegroundColor Red
    exit 1
}
if ($okOut.ToString().Trim() -ne "1") {
    Write-Host "错误：需要 Python $MinMajor.$MinMinor+，当前为 $versionOut。" -ForegroundColor Red
    exit 1
}
Write-Host "使用解释器：$PythonExe ($versionOut)"

# ---- 2. 创建虚拟环境（幂等） ----------------------------------------------
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    Write-Host "已存在虚拟环境：$VenvDir（跳过创建）"
} else {
    Write-Host "创建虚拟环境：$VenvDir"
    & $PythonExe -m venv $VenvDir
    if (-not $?) {
        Write-Host "错误：创建虚拟环境失败。" -ForegroundColor Red
        exit 1
    }
}

# ---- 3 & 4. 升级工具链并安装依赖 ------------------------------------------
Write-Host "升级 pip / setuptools / wheel"
& $VenvPython -m pip install --upgrade pip setuptools wheel
if (-not $?) {
    Write-Host "错误：升级 pip 失败。" -ForegroundColor Red
    exit 1
}

Write-Host "安装项目（可编辑模式）及 dev 额外依赖：.[dev]"
& $VenvPython -m pip install -e ".[dev]"
if (-not $?) {
    Write-Host "错误：安装依赖失败。" -ForegroundColor Red
    exit 1
}

# ---- 5. 提示 ---------------------------------------------------------------
Write-Host ""
Write-Host "完成 ✅ 开发环境已就绪。"
Write-Host "激活虚拟环境："
Write-Host "  .\$VenvDir\Scripts\Activate.ps1"
Write-Host ""
Write-Host "常用命令："
Write-Host "  python -m pytest              # 运行全部测试"
Write-Host "  python -m pytest -m 'not slow'  # 跳过 slow 用例"
Write-Host "  python -m ruff check src      # 静态检查"
Write-Host "  python -m mypy src            # 类型检查"
Write-Host "  pre-commit install            # 安装提交前钩子"
