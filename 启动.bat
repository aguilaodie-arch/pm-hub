@echo off
cd /d "%~dp0"
title Axure 原型发布平台

echo ============================================
echo        Axure 原型发布平台 启动器
echo ============================================
echo.

REM ---- 1. 检查虚拟环境，不存在则自动创建并安装依赖 ----
if not exist ".venv\Scripts\python.exe" (
    echo [初始化] 首次运行，正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 未找到 Python，请先安装 Python 3.10+ 并加入 PATH。
        pause
        exit /b 1
    )
    echo [初始化] 正在安装依赖，使用清华镜像...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
    echo [初始化] 完成！
    echo.
)

REM ---- 2. 检查端口 8000 是否已有实例在运行 ----
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [提示] 检测到服务已在运行，直接为你打开浏览器...
    start "" http://localhost:8000
    echo.
    echo 如需重启服务，请先关闭其他运行中的窗口再启动本脚本。
    pause
    exit /b 0
)

REM ---- 3. 启动服务并自动打开浏览器 ----
echo [启动] 服务启动中，浏览器将自动打开 http://localhost:8000
echo [提示] 关闭本窗口或按 Ctrl+C 即可停止服务。
echo.
start "" /min cmd /c "timeout /t 3 >nul & start http://localhost:8000"

".venv\Scripts\python.exe" run.py

echo.
echo 服务已停止。
pause
