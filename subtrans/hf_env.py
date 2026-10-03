"""HuggingFace 环境准备。

- 模型统一缓存到项目 models/ 目录,便于管理与删除;
- huggingface.co 不可达时自动切换国内镜像 hf-mirror.com。

必须在 import transformers / huggingface_hub 之前调用 setup()。
"""
import os
import socket

from .paths import HF_CACHE_DIR

_configured = False


def _reachable(host, timeout=4):
    try:
        socket.create_connection((host, 443), timeout=timeout).close()
        return True
    except OSError:
        return False


def setup():
    global _configured
    if _configured:
        return
    os.environ.setdefault("HF_HOME", HF_CACHE_DIR)
    # hf-mirror 等国内镜像不支持 Xet 协议,大文件必须走普通 HTTP 下载
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if not os.environ.get("HF_ENDPOINT"):
        if not _reachable("huggingface.co") and _reachable("hf-mirror.com"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    _configured = True
