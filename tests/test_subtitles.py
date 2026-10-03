# -*- coding: utf-8 -*-
"""单元测试:字幕解析、语言检测、可翻译判定、翻译回写、格式保留。"""
import pysubs2

from subtrans import subtitles
from subtrans.subtitles import (_clean, collect_events, detect_language,
                                is_translatable, load, translate_events)


class MockTranslator:
    name = "mock"
    batch_size = 3

    def __init__(self):
        self.received = []

    def translate_batch(self, lines, src_lang, history=None):
        self.received.extend(lines)
        return [f"译[{src_lang}]:{l}" for l in lines]

    def close(self):
        pass


def write(tmp_path, name, content_bytes):
    p = tmp_path / name
    p.write_bytes(content_bytes)
    return str(p)


def test_srt_parse_bom_crlf_multiline(tmp_path):
    raw = ("\ufeff1\n00:00:01,000 --> 00:00:03,500\r\n"
           "危ない!\r\n下がって!\r\n\r\n"
           "2\n00:00:04,000 --> 00:00:06,000\r\n"
           "大丈夫、私がついてるから。\r\n\r\n")
    path = write(tmp_path, "a.srt", raw.encode("utf-8"))
    subs = load(path)
    assert len(subs.events) == 2
    texts = [e.plaintext.replace("\n", "/") for e in subs.events]
    assert texts[0] == "危ない!\n下がって!".replace("\n", "/")
    assert subs.events[0].start == 1000 and subs.events[0].end == 3500


def test_srt_shift_jis(tmp_path):
    raw = "1\n00:00:01,000 --> 00:00:02,000\nありがとう\n\n"
    path = write(tmp_path, "b.srt", raw.encode("shift_jis"))
    subs = load(path)
    assert "ありがとう" in subs.events[0].plaintext


def test_is_translatable_and_clean():
    assert is_translatable("危ない!")
    assert is_translatable("위험해!")
    assert is_translatable("{\\an8}スゴイ")
    assert not is_translatable("12345")
    assert not is_translatable("♪♪♪")
    assert not is_translatable("OPENING THEME")
    assert not is_translatable("...")
    assert _clean("<i>ありがとう</i>") == "ありがとう"
    assert _clean("{\\an8}テスト") == "テスト"


def test_detect_language():
    assert detect_language(["ありがとう", "こんにちは"]) == "ja"
    assert detect_language(["감사합니다", "안녕하세요"]) == "ko"
    assert detect_language(["ありがとう", "감사합니다", "감사합니다"]) == "ko"


def test_translate_events_preserves_timing(tmp_path):
    raw = ("1\n00:00:01,000 --> 00:00:03,500\n危ない!\n\n"
           "2\n00:00:04,000 --> 00:00:06,000\n大丈夫\n\n"
           "3\n00:00:07,000 --> 00:00:08,000\n♪\n\n")
    path = write(tmp_path, "c.srt", raw.encode("utf-8"))
    subs = load(path)
    mock = MockTranslator()
    lang, n = translate_events(subs, mock, "auto")
    assert lang == "ja" and n == 2  # ♪ 行不翻译
    assert subs.events[0].start == 1000 and subs.events[0].end == 3500
    assert subs.events[0].plaintext == "译[ja]:危ない!"
    assert "♪" in subs.events[2].plaintext
    # 重复行去重:危ない 只出现一次
    assert mock.received.count("危ない!") == 1


def test_duplicate_lines_translated_once():
    subs = pysubs2.SSAFile()
    for _ in range(3):
        subs.events.append(pysubs2.SSAEvent(start=0, end=1000, text="はい"))
    mock = MockTranslator()
    translate_events(subs, mock, "ja")
    assert len(mock.received) == 1
    assert all(e.plaintext == "译[ja]:はい" for e in subs.events)


def test_ass_styles_preserved(tmp_path):
    subs = pysubs2.SSAFile()
    subs.styles["OP"] = pysubs2.SSAStyle(fontname="YuGoth", fontsize=48,
                                         primarycolor=pysubs2.Color(255, 0, 0))
    subs.events.append(pysubs2.SSAEvent(start=0, end=2000, text="行こう!",
                                        style="OP"))
    src = str(tmp_path / "d.ass")
    subs.save(src)

    subs2 = load(src)
    mock = MockTranslator()
    translate_events(subs2, mock, "ja")
    out = str(tmp_path / "d.zh.ass")
    subs2.save(out)

    subs3 = load(out)
    assert "OP" in subs3.styles
    assert subs3.styles["OP"].fontsize == 48
    assert subs3.events[0].style == "OP"
    assert subs3.events[0].plaintext.startswith("译[ja]:")


def test_vtt_roundtrip(tmp_path):
    raw = ("WEBVTT\n\n"
           "00:01.000 --> 00:03.000\nありがとう\n\n")
    path = write(tmp_path, "e.vtt", raw.encode("utf-8"))
    subs = load(path)
    translate_events(subs, MockTranslator(), "auto")
    out = str(tmp_path / "e.zh.vtt")
    subs.save(out)
    text = open(out, encoding="utf-8").read()
    assert "译[ja]:ありがとう" in text


def test_empty_and_bad_files(tmp_path):
    path = write(tmp_path, "empty.srt", b"")
    subs = load(path)
    lang, n = translate_events(subs, MockTranslator(), "auto")
    assert n == 0

    path2 = write(tmp_path, "bad.bin", b"\xff\xfe\x00\x99\x88")
    try:
        load(path2)
        assert False, "应当抛出解码错误"
    except ValueError:
        pass
