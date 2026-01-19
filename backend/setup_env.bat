@echo off
REM ============================================================================
REM 虚拟环境搭建脚本 (Windows CMD)
REM ============================================================================
REM 使用方法: 在 backend 目录下运行 setup_env.bat
REM 要求: Python 3.13.3 已安装
REM ============================================================================

echo ========================================
echo CNPE 图纸处理系统 - 环境搭建
echo ========================================

REM 1. 检查 Python 版本
echo.
echo [1/6] 检查 Python 版本...
python --version
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.13.3
    echo 下载地址: https://www.python.org/downloads/release/python-3133/
    pause
    exit /b 1
)

REM 2. 删除旧的虚拟环境
echo.
echo [2/6] 清理旧环境...
if exist .venv (
    echo   删除旧的 .venv 目录...
    rmdir /s /q .venv
)

REM 3. 创建新的虚拟环境
echo.
echo [3/6] 创建虚拟环境...
python -m venv .venv

if not exist .venv\Scripts\python.exe (
    echo 错误: 虚拟环境创建失败
    pause
    exit /b 1
)
echo   虚拟环境创建成功: .venv\

REM 4. 激活虚拟环境
echo.
echo [4/6] 激活虚拟环境...
call .venv\Scripts\activate.bat

REM 5. 升级 pip 并安装依赖
echo.
echo [5/6] 安装依赖...

echo   升级 pip...
python -m pip install --upgrade pip setuptools wheel --quiet

echo   安装生产依赖...
pip install -r requirements.txt --quiet

echo   安装开发依赖...
pip install -r requirements-dev.txt --quiet

echo   安装 pywin32 (Windows COM)...
pip install pywin32>=308 --quiet

echo   以开发模式安装项目...
pip install -e . --quiet

echo   依赖安装完成

REM 6. 验证安装
echo.
echo [6/6] 验证安装...
python --version
pip list

echo.
echo ========================================
echo 环境搭建完成！
echo ========================================

echo.
echo 后续步骤:
echo   1. 激活环境: .venv\Scripts\activate.bat
echo   2. 运行测试: pytest tests/unit/ -v
echo   3. 开始开发!

pause
