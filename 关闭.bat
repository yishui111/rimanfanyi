@echo off
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
