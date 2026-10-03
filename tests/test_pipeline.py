# -*- coding: utf-8 -*-
"""单元测试:流水线集成(Mock 翻译器 + 真实 pysubs2/ffmpeg 路径)。"""
import os

import pysubs2
import pytest

from subtrans import pipeline, subtitles


class MockTranslator:
    name = "mock"
    batch_size = 4

    def translate_batch(self, lines, src_lang, history=None):
        return [f"中:{l}" for l in lines]

    def close(self):
        pass


@pytest.fixture
def mock_backend(monkeypatch):
    monkeypatch.setattr(pipeline, "get_translator", lambda cfg, reload=False: MockTranslator())


def test_translate_subtitle_file(tmp_path, mock_backend):
    src = tmp_path / "ep01.srt"
    src.write_text("1\n00:00:01,000 --> 00:00:02,000\nありがとう\n\n", encoding="utf-8")
    r = pipeline.translate_subtitle(str(src), cfg={}, src_lang="ja")
    assert r["lines"] == 1 and r["lang"] == "ja"
    out = tmp_path / "ep01.zh.srt"
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "中:ありがとう" in text
    assert "00:00:01,000 --> 00:00:02,000" in text


def test_translate_subtitle_auto_lang_ko(tmp_path, mock_backend):
    src = tmp_path / "webtoon.ass"
    subs = pysubs2.SSAFile()
    subs.events.append(pysubs2.SSAEvent(start=0, end=1500, text="안녕하세요!"))
    subs.save(str(src))
    r = pipeline.translate_subtitle(str(src), cfg={}, src_lang="auto")
    assert r["lang"] == "ko"


def test_translate_video_rejects_silence(tmp_path, mock_backend, monkeypatch):
    # ASR 未识别到任何语音(纯静音视频)时,流水线应报错而不是输出空字幕
    import subprocess
    silent = str(tmp_path / "silent.mp4")
    subprocess.check_call(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                           "-f", "lavfi", "-i", "color=c=black:s=320x240:d=2",
                           "-t", "2", "-map", "1:v", "-map", "0:a",
                           "-c:v", "libx264", "-preset", "ultrafast", silent])
    # 真实静音音频经 whisper/VAD 后不会产生任何段;此处用等价 mock 验证流水线的报错分支
    monkeypatch.setattr(pipeline.asr, "transcribe",
                        lambda *a, **k: ([], "ja", {"model": "mock"}))
    with pytest.raises(RuntimeError, match="未识别到任何语音"):
        pipeline.translate_video(silent, cfg={}, src_lang="ja")
