"""翻译后端工厂:按配置与运行环境自动选择。

优先级:api 配置 > 本机 Ollama 服务 > 本地 NLLB 翻译模型。
"""
import logging

import httpx

from .llm_api import LlmApiTranslator
from .nllb import NllbTranslator

logger = logging.getLogger(__name__)


def resolve_ollama_model(cfg):
    """返回 Ollama 服务器上实际存在的模型名;不可用则返回 None。

    配置写 "qwen2.5:7b" 时,服务器上的 "qwen2.5:7b-16k" 也会按前缀匹配上。
    """
    try:
        r = httpx.get(f"{cfg['ollama']['base_url'].rstrip('/')}/api/tags", timeout=3)
        names = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        return None
    want = cfg["ollama"]["model"]
    if want in names:
        return want
    prefix = want.split(":")[0]
    for n in names:
        if n.split(":")[0] == prefix:
            return n
    return None


def detect_backend(cfg):
    """返回 (backend, 选择原因)。backend: "nllb" | "api"。"""
    mode = cfg.get("translation_backend", "auto")
    if mode == "nllb":
        return "nllb", "配置指定 nllb"
    if mode == "api":
        return "api", "配置指定 api"
    api = cfg.get("api", {})
    if api.get("base_url") and api.get("model"):
        return "api", "检测到 api.base_url 配置"
    if resolve_ollama_model(cfg):
        return "api", "检测到本机 Ollama 服务"
    return "nllb", "未配置 LLM 接口,使用本地 NLLB 翻译模型"


def create_translator(cfg):
    backend, why = detect_backend(cfg)
    logger.info("翻译后端:%s(%s)", backend, why)
    if backend == "api":
        api = dict(cfg["api"])
        if not (api.get("base_url") and api.get("model")):
            api["base_url"] = cfg["ollama"]["base_url"].rstrip("/") + "/v1"
            api["model"] = resolve_ollama_model(cfg)  # 用服务器上的真实模型名
        tr = LlmApiTranslator(api)
        tr.backend_name = f"LLM({api['model']} @ {api['base_url']})"
    else:
        tr = NllbTranslator(cfg["nllb"])
        tr.backend_name = f"NLLB({cfg['nllb']['model_id']})"
    return tr
