"""config.json 读写与默认配置。"""
import copy
import json
import os

from .paths import CONFIG_FILE, ensure_dirs

DEFAULTS = {
    # 翻译后端: auto(自动检测) | nllb(本地NLLB翻译模型) | api(OpenAI兼容接口)
    "translation_backend": "auto",
    "api": {
        # 例: DeepSeek https://api.deepseek.com/v1 (model: deepseek-chat)
        #      本地Ollama  http://127.0.0.1:11434/v1 (model: qwen2.5:7b-instruct)
        "base_url": "",
        "api_key": "",
        "model": "",
        "temperature": 0.2,
        "batch_size": 20,
        "context_lines": 2,
        "max_retries": 2,
        "timeout": 120,
    },
    "ollama": {
        "base_url": "http://127.0.0.1:11434",
        "model": "qwen2.5:7b-instruct",
    },
    "nllb": {
        "model_id": "facebook/nllb-200-distilled-600M",
        "device": "auto",
        "beam_size": 4,
        "batch_size": 32,
    },
    "asr": {
        # auto: 有NVIDIA显卡用 large-v3(最准),否则用 small
        "model_size": "auto",
        "device": "auto",
        "compute_type": "auto",
        "beam_size": 5,
        "language": "auto",
        # CPU 识别线程数(留空跟随 CTranslate2 默认;多核 CPU 建议 8)
        "cpu_threads": None,
        # 老片/强 BGM 片源若"未识别到任何语音",可调低 VAD 阈值(0.5→0.2)提高灵敏度
        "vad_threshold": None,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 7860,
        # 启动时预热翻译模型(占用少量显存;关闭.bat 会完整释放)
        "preload": True,
    },
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    ensure_dirs()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
        except (OSError, json.JSONDecodeError):
            user = {}
        return _merge(DEFAULTS, user)
    cfg = copy.deepcopy(DEFAULTS)
    save(cfg)
    return cfg


def save(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
