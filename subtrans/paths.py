"""项目路径常量。"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
HF_CACHE_DIR = os.path.join(MODELS_DIR, "hf")
WHISPER_DIR = os.path.join(MODELS_DIR, "whisper")
RUNTIME_DIR = os.path.join(PROJECT_ROOT, "runtime")
PID_FILE = os.path.join(RUNTIME_DIR, "server.pid")
LOG_FILE = os.path.join(RUNTIME_DIR, "server.log")
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.json")

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".ts", ".m4v", ".rmvb"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".vtt"}


def ensure_dirs():
    for d in (MODELS_DIR, HF_CACHE_DIR, WHISPER_DIR, RUNTIME_DIR):
        os.makedirs(d, exist_ok=True)


def is_ascii_root():
    """项目路径是否纯 ASCII。

    实测发现:项目装在含中文的路径下时,部分安全软件(如火绒行为防御)会把
    "非 ASCII 路径 + 大模型文件加载"误判并静默终止进程(无任何报错,进程直接消失,
    ≥1.5GB 的模型必现,≤484MB 的小模型正常)。放纯英文路径或用目录联接可绕开。
    """
    try:
        PROJECT_ROOT.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False
