# ============================================================================
# 虚拟环境搭建脚本 (Windows PowerShell)
# ============================================================================
# 使用方法: 在 backend 目录下运行 .\setup_env.ps1
# 要求: Python 3.13.3 已安装
# ============================================================================

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CNPE 图纸处理系统 - 环境搭建" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 检查 Python 版本
Write-Host "`n[1/6] 检查 Python 版本..." -ForegroundColor Yellow

$pythonCmd = "python"
try {
    $version = & $pythonCmd --version 2>&1
    Write-Host "  找到: $version" -ForegroundColor Green
    
    if ($version -notmatch "3\.13") {
        Write-Host "  警告: 建议使用 Python 3.13.x，当前版本可能存在兼容性问题" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  错误: 未找到 Python，请先安装 Python 3.13.3" -ForegroundColor Red
    Write-Host "  下载地址: https://www.python.org/downloads/release/python-3133/" -ForegroundColor Yellow
    exit 1
}

# 2. 删除旧的虚拟环境（如存在）
Write-Host "`n[2/6] 清理旧环境..." -ForegroundColor Yellow

if (Test-Path ".venv") {
    Write-Host "  删除旧的 .venv 目录..." -ForegroundColor Gray
    Remove-Item -Recurse -Force ".venv"
}

# 3. 创建新的虚拟环境
Write-Host "`n[3/6] 创建虚拟环境..." -ForegroundColor Yellow

& $pythonCmd -m venv .venv

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "  错误: 虚拟环境创建失败" -ForegroundColor Red
    exit 1
}
Write-Host "  虚拟环境创建成功: .venv\" -ForegroundColor Green

# 4. 激活虚拟环境
Write-Host "`n[4/6] 激活虚拟环境..." -ForegroundColor Yellow

& ".venv\Scripts\Activate.ps1"
Write-Host "  虚拟环境已激活" -ForegroundColor Green

# 5. 升级 pip 并安装依赖
Write-Host "`n[5/6] 安装依赖..." -ForegroundColor Yellow

Write-Host "  升级 pip..." -ForegroundColor Gray
& python -m pip install --upgrade pip setuptools wheel --quiet

Write-Host "  安装生产依赖..." -ForegroundColor Gray
& pip install -r requirements.txt --quiet

Write-Host "  安装开发依赖..." -ForegroundColor Gray
& pip install -r requirements-dev.txt --quiet

# Windows 专用: 安装 pywin32
Write-Host "  安装 pywin32 (Windows COM)..." -ForegroundColor Gray
& pip install pywin32>=308 --quiet

# 以开发模式安装项目
Write-Host "  以开发模式安装项目..." -ForegroundColor Gray
& pip install -e . --quiet

Write-Host "  依赖安装完成" -ForegroundColor Green

# 6. 验证安装
Write-Host "`n[6/6] 验证安装..." -ForegroundColor Yellow

Write-Host "  Python 路径: $(Get-Command python | Select-Object -ExpandProperty Source)" -ForegroundColor Gray
Write-Host "  Python 版本: $(python --version)" -ForegroundColor Gray

# 测试关键库导入
$testScript = @"
import sys
print(f'  Python: {sys.version}')

try:
    import fastapi; print(f'  fastapi: {fastapi.__version__}')
except: print('  fastapi: 导入失败')

try:
    import pydantic; print(f'  pydantic: {pydantic.__version__}')
except: print('  pydantic: 导入失败')

try:
    import ezdxf; print(f'  ezdxf: {ezdxf.__version__}')
except: print('  ezdxf: 导入失败')

try:
    import openpyxl; print(f'  openpyxl: {openpyxl.__version__}')
except: print('  openpyxl: 导入失败')

try:
    import docx; print(f'  python-docx: OK')
except: print('  python-docx: 导入失败')

try:
    import pypdf; print(f'  pypdf: {pypdf.__version__}')
except: print('  pypdf: 导入失败')

try:
    import win32com; print(f'  pywin32: OK')
except: print('  pywin32: 导入失败 (Windows COM 不可用)')

try:
    import pytest; print(f'  pytest: {pytest.__version__}')
except: print('  pytest: 导入失败')
"@

& python -c $testScript

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "环境搭建完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n后续步骤:" -ForegroundColor Yellow
Write-Host "  1. 激活环境: .venv\Scripts\Activate.ps1" -ForegroundColor Gray
Write-Host "  2. 运行测试: pytest tests/unit/ -v" -ForegroundColor Gray
Write-Host "  3. 开始开发!" -ForegroundColor Gray
