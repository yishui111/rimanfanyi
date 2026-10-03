# -*- coding: utf-8 -*-
"""单元测试:LLM 编号输出解析、后端工厂选择逻辑。"""
import pytest

from subtrans.translate.llm_api import LlmApiTranslator
from subtrans.translate import detect_backend


def test_parse_numbered_normal():
    reply = "1|你好\n2|再见\n3|谢谢"
    out = LlmApiTranslator.parse_numbered(reply, 3)
    assert out == {1: "你好", 2: "再见", 3: "谢谢"}


def test_parse_numbered_variants():
    reply = " 1 |你好\n2:再见\n3｜谢谢\n4、不用"
    out = LlmApiTranslator.parse_numbered(reply, 4)
    assert out[1] == "你好"
    assert out[2] == "再见"
    assert out[3] == "谢谢"
    assert 4 not in out  # 顿号分隔不认,交由单行重试


def test_parse_numbered_out_of_range_and_dup():
    reply = "1|A\n1|B\n9|X\n2|C"
    out = LlmApiTranslator.parse_numbered(reply, 2)
    assert out == {1: "A", 2: "C"}


def test_parse_numbered_multiline_translation_keeps_first():
    reply = "1|你好\n这是第二行\n2|再见"
    out = LlmApiTranslator.parse_numbered(reply, 2)
    assert out[1] == "你好"


@pytest.fixture
def api_tr():
    return LlmApiTranslator({"base_url": "http://127.0.0.1:9/v1", "api_key": "x",
                             "model": "m", "max_retries": 0, "timeout": 5})


def test_api_single_line_fallback_on_garbage(api_tr, monkeypatch):
    api_tr.client = None

    def fake_post(messages):
        # 批量回复不带编号 -> 转单行重试;单行也返回空 -> 原文兜底,绝不丢行
        if "把这句" in messages[-1]["content"]:
            return ""
        return "完全不带编号的回复"

    monkeypatch.setattr(api_tr, "_chat", fake_post)
    res = api_tr.translate_batch(["危ない"], "ja")
    assert res == ["危ない"]


class FakeCfg(dict):
    pass


def _cfg(**kw):
    base = {"translation_backend": "auto",
            "api": {"base_url": "", "model": ""},
            "ollama": {"base_url": "http://127.0.0.1:1", "model": "qwen2.5:7b-instruct"}}
    base.update(kw)
    return base


def test_detect_backend_nllb_default():
    assert detect_backend(_cfg())[0] == "nllb"


def test_detect_backend_api_configured():
    cfg = _cfg()
    cfg["api"] = {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"}
    assert detect_backend(cfg)[0] == "api"
