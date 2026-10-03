"""NLLB-200 本地翻译后端。

Meta 开源的多语言翻译模型,600M 参数即可在 4080 显卡上高速推理,
原生支持 日语(jpn_Jpan)/韩语(kor_Hang) -> 简体中文(zho_Hans)。
"""
import gc
import logging

from .. import hf_env
from ..subtitles import _HANGUL_RE

hf_env.setup()

logger = logging.getLogger(__name__)

NLLB_CODES = {"ja": "jpn_Jpan", "ko": "kor_Hang"}
TARGET = "zho_Hans"


class NllbTranslator:
    name = "nllb"
    batch_size = 32

    def __init__(self, cfg):
        import torch
        import transformers
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self._torch = torch
        model_id = cfg["model_id"]
        device = cfg.get("device", "auto")
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        dtype = torch.float16 if device == "cuda" else torch.float32
        # transformers 5.x 把 torch_dtype 改名为 dtype
        dtype_kw = {"dtype": dtype} if int(transformers.__version__.split(".")[0]) >= 5 \
            else {"torch_dtype": dtype}

        logger.info("加载 NLLB 翻译模型 %s -> %s(transformers %s)...",
                    model_id, device, transformers.__version__)
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_id, **dtype_kw)
        self.model.to(device)
        self.model.eval()
        self.beam_size = int(cfg.get("beam_size", 4))

    def warmup(self):
        self.translate_batch(["テスト"], "ja")

    @staticmethod
    def _detect(text):
        return "ko" if _HANGUL_RE.search(text) else "ja"

    def translate_batch(self, lines, src_lang, history=None):
        torch = self._torch
        results = [None] * len(lines)
        groups = {}
        for i, line in enumerate(lines):
            code = NLLB_CODES.get(src_lang) or NLLB_CODES[self._detect(line)]
            groups.setdefault(code, []).append(i)

        for code, idxs in groups.items():
            batch = [lines[i] for i in idxs]
            self.tokenizer.src_lang = code
            enc = self.tokenizer(batch, return_tensors="pt", padding=True,
                                 truncation=True, max_length=256).to(self.device)
            with torch.no_grad():
                out = self.model.generate(
                    **enc,
                    forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(TARGET),
                    max_new_tokens=256,
                    num_beams=self.beam_size,
                )
            for i, text in zip(idxs, self.tokenizer.batch_decode(out, skip_special_tokens=True)):
                results[i] = text.strip()
        return results

    def close(self):
        self.model = None
        self.tokenizer = None
        try:
            self._torch.cuda.empty_cache()
        except Exception:
            pass
        gc.collect()
