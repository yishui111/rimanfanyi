# -*- coding: utf-8 -*-
"""生成 启动.bat / 关闭.bat(GBK 编码,兼容中文版 cmd)。"""
import os

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

START_BAT = r"""@echo off
chcp 936 >nul
title 动漫字幕翻译服务 - 启动
cd /d "%~dp0"
set PYTHONIOENCODING=:replace

if exist ".venv\Scripts\python.exe" goto :deps
echo [初始化] 首次运行:正在创建虚拟环境...
where py >nul 2>nul
if errorlevel 1 (python -m venv .venv) else (py -3.12 -m venv .venv)
if not exist ".venv\Scripts\python.exe" goto :nopython

:deps
if exist ".venv\.deps_ok" goto :run
if not exist "runtime" mkdir "runtime"
echo [初始化] 正在安装依赖(首次约10-30分钟,取决于网速),请勿关闭本窗口...
".venv\Scripts\python.exe" -m pip install -U pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err
".venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cu124
".venv\Scripts\python.exe" -c "import faster_whisper, transformers, gradio, pysubs2" 2> "runtime\deps_err.txt"
if errorlevel 1 (
    rem 偶发的杀毒/索引扫描会短暂锁住新装文件,3 秒后重试一次
    ping -n 4 127.0.0.1 >nul
    ".venv\Scripts\python.exe" -c "import faster_whisper, transformers, gradio, pysubs2" 2>> "runtime\deps_err.txt"
    if errorlevel 1 (type "runtime\deps_err.txt" & goto :err)
)
echo ok> ".venv\.deps_ok"

:run
echo [启动] 浏览器将自动打开 http://127.0.0.1:7860
echo [提示] 关闭服务请双击 关闭.bat(会释放显存和内存)
".venv\Scripts\python.exe" -X utf8 -m subtrans.server
echo.
echo [!] 服务已退出。
pause
exit /b 0

:nopython
echo [错误] 未检测到 Python,请先安装 Python 3.10~3.12 后重试。
pause
exit /b 1

:err
echo [错误] 依赖安装失败,请检查网络后重试(删除 .venv\.deps_ok 可重新安装)。
pause
exit /b 1
"""

STOP_BAT = r"""@echo off
chcp 936 >nul
setlocal EnableDelayedExpansion
title 动漫字幕翻译服务 - 关闭
cd /d "%~dp0"
echo 正在停止服务...

set SPID=
if exist "runtime\server.pid" set /p SPID=<"runtime\server.pid"
if defined SPID (
    echo   结束主进程 PID !SPID! ...
    taskkill /PID !SPID! /T /F >nul 2>&1
)
if exist "runtime\server.pid" del "runtime\server.pid" >nul 2>&1

rem 兜底:清理所有由本项目虚拟环境启动的 python 进程
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match '\.venv' -and $_.CommandLine -match 'subtrans' } | ForEach-Object { Write-Host ('  结束残留进程 ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

rem 用 ping 做延时,避免 PATH 里有 GNU timeout 时冲突
ping -n 3 127.0.0.1 >nul

set LISTEN=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :7860 ^| findstr LISTENING') do set LISTEN=%%a
if defined LISTEN (
    echo [警告] 端口 7860 仍被 PID !LISTEN! 占用,尝试强制结束...
    taskkill /PID !LISTEN! /T /F >nul 2>&1
    ping -n 2 127.0.0.1 >nul
) else (
    echo [OK] 端口 7860 已释放,服务进程已全部退出。
)

echo.
echo 当前显存占用(应回到桌面基线水平):
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>nul
echo.
echo 关闭完成,显存与内存已随进程退出而释放。
pause
exit /b 0
"""


def write_gbk(name, content):
    path = os.path.join(PROJ, name)
    with open(path, "w", encoding="gbk", newline="\r\n") as f:
        f.write(content)
    print("written:", path)


if __name__ == "__main__":
    write_gbk("启动.bat", START_BAT)
    write_gbk("关闭.bat", STOP_BAT)
