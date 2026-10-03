"""OpenAI 兼容 Chat API 翻译后端。

可接入任意大模型:DeepSeek / GLM / 本地 Ollama(http://127.0.0.1:11434/v1)等。
带编号批量翻译 + 上下文保持人名一致 + 解析失败单行重试。
"""
import logging
import re
import time

import httpx

from .base import TranslatorBase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位资深动漫字幕翻译官,精通日语、韩语和中文。"
    "把用户给出的编号字幕行翻译成简体中文:口语化、自然、符合动漫/韩剧语境,"
    "保持原文语气与人名一致;不要合并、拆分或遗漏任何编号;"
    "每行严格按「编号|译文」格式输出,不要输出任何解释。"
)
_NUM_RE = re.compile(r"^\s*(\d+)\s*[|｜:：]\s*(.*)$")


class LlmApiTranslator(TranslatorBase):
    name = "api"
    batch_size = 20

    def __init__(self, cfg):
        self.base_url = cfg["base_url"].rstrip("/")
        self.api_key = cfg.get("api_key") or "EMPTY"
        self.model = cfg["model"]
        self.temperature = float(cfg.get("temperature", 0.2))
        self.batch_size = int(cfg.get("batch_size", 20))
        self.context_lines = int(cfg.get("context_lines", 2))
        self.max_retries = int(cfg.get("max_retries", 2))
        self.timeout = float(cfg.get("timeout", 120))
        self.client = httpx.Client(timeout=self.timeout)

    def _chat(self, messages):
        payload = {"model": self.model, "messages": messages,
                   "temperature": self.temperature}
        is_ollama = "11434" in self.base_url
        if is_ollama:
            payload["keep_alive"] = 0
        resp = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        if is_ollama:
            # OpenAI 兼容端点可能忽略 keep_alive,再用原生接口主动卸载模型释放显存
            try:
                self.client.post(
                    self.base_url.replace("/v1", "") + "/api/generate",
                    json={"model": self.model, "keep_alive": 0}, timeout=15)
            except Exception:
                pass
        return content

    @staticmethod
    def parse_numbered(reply, expect):
        """把「1|译文」样式的回复解析回 {行号: 译文}。"""
        out = {}
        for raw in reply.splitlines():
            m = _NUM_RE.match(raw.strip())
            if m:
                idx = int(m.group(1))
                if 1 <= idx <= expect and idx not in out:
                    out[idx] = m.group(2).strip()
        return out

    def translate_batch(self, lines, src_lang, history=None):
        lang_name = {"ja": "日语", "ko": "韩语", "zh": "中文"}.get(src_lang, src_lang)
        body = "\n".join(f"{i + 1}|{l}" for i, l in enumerate(lines))
        context = ""
        if history:
            ctx = [f"{s} => {t}" for s, t in history[-self.context_lines:]]
            if ctx:
                context = "前文翻译(供参考,保持人名与语气一致):\n" + "\n".join(ctx) + "\n\n"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": f"{context}请把以下{lang_name}字幕翻译成简体中文:\n{body}"},
        ]
        reply = self._chat(messages)
        parsed = self.parse_numbered(reply, len(lines))

        results, missing = [], []
        for i, line in enumerate(lines):
            v = parsed.get(i + 1)
            if v:
                results.append(v)
            else:
                missing.append(i)
                results.append(None)

        for i in missing:  # 解析失败的行单独重试
            v = self._translate_one(lines[i], lang_name)
            results[i] = v if v is not None else lines[i]
        return results

    def _translate_one(self, line, lang_name):
        messages = [
            {"role": "system", "content": "你是专业动漫字幕翻译官。只输出译文本身,不要解释。"},
            {"role": "user", "content": f"把这句{lang_name}翻译成简体中文:{line}"},
        ]
        for attempt in range(self.max_retries + 1):
            try:
                out = self._chat(messages).strip()
                if out:
                    return out.splitlines()[0]
            except Exception as e:
                logger.warning("单行重试失败(%d/%d): %s", attempt + 1, self.max_retries + 1, e)
                time.sleep(1)
        return None

    def warmup(self):
        """发一条真实请求,让本机 Ollama 预先加载模型(请求完自动卸载)。"""
        self.translate_batch(["テスト"], "ja")

    def close(self):
        self.client.close()
