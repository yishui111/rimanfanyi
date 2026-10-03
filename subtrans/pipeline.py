"""流水线:视频 -> 中文字幕;字幕文件 -> 中文字幕。"""
import logging
import os
import threading
import time

import pysubs2

from . import asr, subtitles
from .config import DEFAULTS, _merge
from .translate import create_translator

logger = logging.getLogger(__name__)

_translator = None
_lock = threading.Lock()


def _full_cfg(cfg):
    """允许调用方只传部分配置,缺省项用默认值补齐。"""
    return _merge(DEFAULTS, cfg or {})


def get_translator(cfg, reload=False):
    global _translator
    with _lock:
        if _translator is None or reload:
            if _translator is not None:
                _translator.close()
            _translator = create_translator(cfg)
        return _translator


def release_translator():
    """释放翻译模型占用的显存/内存(关闭服务时由进程退出自动兜底)。"""
    global _translator
    with _lock:
        if _translator is not None:
            _translator.close()
            _translator = None
            logger.info("翻译模型已释放")


def _events_from_segments(segments):
    return [pysubs2.SSAEvent(start=int(s["start"] * 1000), end=int(s["end"] * 1000),
                             text=s["text"]) for s in segments]


def translate_video(video_path, cfg, src_lang="auto", keep_source=True, progress=None):
    """视频 -> 语音识别 -> 翻译,输出 <同名>.zh.srt(可选 <同名>.<语言>.srt)。"""
    cfg = _full_cfg(cfg)
    tm = {}

    def asr_prog(f, d):
        if progress:
            progress(f * 0.6, f"语音识别:{d}")

    t0 = time.time()
    segments, detected, asr_info = asr.transcribe(video_path, cfg["asr"], src_lang, asr_prog)
    tm["asr"] = time.time() - t0
    if not segments:
        raise RuntimeError("未识别到任何语音(可能视频没有对白,或音轨为空)")

    base, _ = os.path.splitext(video_path)
    src_srt = None
    if keep_source:
        src_srt = f"{base}.{detected}.srt"
        f = pysubs2.SSAFile()
        f.events = _events_from_segments(segments)
        f.save(src_srt)

    def tr_prog(f_, d):
        if progress:
            progress(0.6 + f_ * 0.4, f"翻译:{d}")

    sub = pysubs2.SSAFile()
    sub.events = _events_from_segments(segments)
    translator = get_translator(cfg)
    t1 = time.time()
    subtitles.translate_events(sub, translator, detected or src_lang, tr_prog)
    tm["translate"] = time.time() - t1
    zh_srt = f"{base}.zh.srt"
    sub.save(zh_srt)

    result = {"video": video_path, "zh_srt": zh_srt, "src_srt": src_srt,
              "detected": detected, "asr": asr_info, "lines": len(segments),
              "timings": tm}
    logger.info("完成:%s(识别 %d 行,%s)", zh_srt, len(segments), detected)
    return result


def translate_subtitle(path, cfg, src_lang="auto", progress=None, out_path=None):
    """翻译已有字幕文件(SRT/ASS/VTT),输出 <同名>.zh.<原格式>。"""
    cfg = _full_cfg(cfg)
    sub = subtitles.load(path)
    translator = get_translator(cfg)
    detected, n = subtitles.translate_events(sub, translator, src_lang, progress)
    if out_path is None:
        root, ext = os.path.splitext(path)
        out_path = f"{root}.zh{ext}"
    sub.save(out_path)
    logger.info("完成:%s(%d 行,%s)", out_path, n, detected)
    return {"input": path, "output": out_path, "lang": detected, "lines": n}
