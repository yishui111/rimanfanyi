@echo off
chcp 936 >nul
title 动漫字幕翻译服务 - 启动
cd /d "%~dp0"
set PYTHONIOENCODING=:replace
rem 模型与临时文件一律留在本项目文件夹内，不占 C 盘
set "HF_HOME=%~dp0hf-cache"
if not exist "%~dp0hf-cache" mkdir "%~dp0hf-cache"
if not exist "%~dp0runtime\tmp" mkdir "%~dp0runtime\tmp"
set "TMP=%~dp0runtime\tmp"
set "TEMP=%~dp0runtime\tmp"

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
