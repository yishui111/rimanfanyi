# -*- coding: utf-8 -*-
"""下载模型:NLLB 翻译模型 + faster-whisper large-v3(自动走国内镜像)。"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

from subtrans import hf_env, paths          # noqa: E402

hf_env.setup()
paths.ensure_dirs()

from huggingface_hub import snapshot_download   # noqa: E402

print("endpoint:", os.environ.get("HF_ENDPOINT", "https://huggingface.co"))

print("== 1/2 下载 NLLB-200-distilled-600M(翻译模型,约2.4GB)==")
snapshot_download("facebook/nllb-200-distilled-600M",
                  allow_patterns=["*.json", "*.model", "*.bin",
                                  "special_tokens_map.json", "tokenizer*"])
print("NLLB 下载完成")

print("== 2/2 下载 faster-whisper large-v3(语音识别,约3GB)==")
snapshot_download("Systran/faster-whisper-large-v3")
print("whisper 下载完成")
print("MODELS_DONE")
