"""faster-whisper 语音识别:视频/音频 -> 带时间轴的文本。"""
import logging
import os
import threading

from . import hf_env, paths

hf_env.setup()

logger = logging.getLogger(__name__)

_model_cache = {}
_model_lock = threading.Lock()

_av_patched = False


def _patch_av():
    """av 19 移除了 av.open 的 metadata_errors 参数,faster-whisper 1.2.1 仍在传
    —— 加垫片兼容,语义不变(仅忽略损坏元数据)。"""
    global _av_patched
    if _av_patched:
        return
    import av
    orig_open = av.open

    def open_compat(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return orig_open(*args, **kwargs)

    av.open = open_compat
    _av_patched = True


def _torch_dll_dir():
    """让 CTranslate2 找到 torch 自带的 cuBLAS/cuDNN DLL(Windows 必要)。"""
    try:
        import torch
        lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(lib):
            os.add_dll_directory(lib)
            return True
    except ImportError:
        pass
    return False


def _pick_config(cfg):
    import ctranslate2
    has_cuda = ctranslate2.get_cuda_device_count() > 0
    device = cfg.get("device", "auto")
    if device == "auto":
        device = "cuda" if has_cuda else "cpu"
    size = cfg.get("model_size", "auto")
    if size == "auto":
        size = "large-v3" if device == "cuda" else "small"
    ctype = cfg.get("compute_type", "auto")
    if ctype == "auto":
        ctype = "int8_float16" if device == "cuda" else "int8"
    return size, device, ctype


def load_model(cfg, device_override=None):
    from faster_whisper import WhisperModel

    _patch_av()
    size, device, ctype = _pick_config(cfg)
    if device_override:
        device = device_override
        if device == "cpu" and ctype == "int8_float16":
            ctype = "int8"
    key = (size, device, ctype)
    with _model_lock:
        if key in _model_cache:
            return _model_cache[key], {"model": size, "device": device,
                                       "compute_type": ctype}

    _torch_dll_dir()
    logger.info("加载 Whisper 模型 %s(device=%s, compute=%s)...", size, device, ctype)
    # CPU 推理线程数可配(CTranslate2 默认仅用 4 线程,多核机器值得调大)
    extra = {}
    if device == "cpu" and cfg.get("cpu_threads"):
        extra["cpu_threads"] = int(cfg["cpu_threads"])
    try:
        model = WhisperModel(size, device=device, compute_type=ctype,
                             download_root=paths.WHISPER_DIR, **extra)
    except Exception as e:
        if device == "cuda":
            logger.warning("CUDA 加载失败(%s),回退到 CPU。", e)
            device, ctype = "cpu", "int8"
            key = (size, device, ctype)
            model = WhisperModel(size, device=device, compute_type=ctype,
                                 download_root=paths.WHISPER_DIR, **extra)
        else:
            raise
    with _model_lock:
        _model_cache[key] = model
    return model, {"model": size, "device": device, "compute_type": ctype}


def _extract_audio(video_path):
    """优先用系统 ffmpeg 抽取 16kHz 单声道 wav,再交给 whisper。

    进程内 PyAV 解码对部分封装/编码(实测 AV1+Opus 的 mp4)在特定环境下不稳定,
    外部 ffmpeg 支持的容器与编码更全,失败时自动回退原路径(由 PyAV 解码)。
    返回临时 wav 路径或 None;调用方负责用完删除。
    """
    import shutil
    import subprocess
    import tempfile

    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        r = subprocess.run(
            [exe, "-v", "error", "-y", "-i", video_path, "-vn",
             "-ac", "1", "-ar", "16000", "-f", "wav", wav],
            capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        r = None
    if r is not None and r.returncode == 0 and os.path.getsize(wav) > 44:
        return wav
    try:
        os.remove(wav)
    except OSError:
        pass
    return None


def transcribe(video_path, cfg, language="auto", progress=None):
    """返回 (segments[dict], detected_lang, info)。

    CUDA 故障有两种形态:模型加载时抛异常(此处直接回退 CPU),以及首次计算时
    才抛 cuBLAS/cuDNN 错误——后者也要回退 CPU 重跑,不能只依赖 load_model 的回退。
    """
    try:
        return _transcribe_on(video_path, cfg, language, progress, device_override=None)
    except Exception as e:
        if _is_cuda_error(e) and cfg.get("device", "auto") != "cpu":
            logger.warning("CUDA 计算失败(%s),改用 CPU 重试。", e)
            return _transcribe_on(video_path, cfg, language, progress,
                                  device_override="cpu")
        raise


def _is_cuda_error(e):
    msg = str(e).lower()
    return any(k in msg for k in ("cublas", "cudnn", "cuda error", "cuda failure",
                                  "no kernel image"))


def _transcribe_on(video_path, cfg, language, progress, device_override):
    model, info_cfg = load_model(cfg, device_override=device_override)
    lang = None if language in ("auto", "", None) else language
    tmp_wav = _extract_audio(video_path)
    if tmp_wav:
        logger.info("音频已抽取:%s", tmp_wav)
        asr_input = tmp_wav
    else:
        asr_input = video_path
    try:
        vad_params = {"min_silence_duration_ms": 500}
        # 老片/强 BGM 下默认阈值(0.5)可能把全部音频判为非语音,允许调低
        if cfg.get("vad_threshold"):
            vad_params["threshold"] = float(cfg["vad_threshold"])
        segments_iter, info = model.transcribe(
            asr_input,
            language=lang,
            beam_size=int(cfg.get("beam_size", 5)),
            vad_filter=True,
            vad_parameters=vad_params,
            condition_on_previous_text=False,
        )
        out = []
        duration = max(info.duration, 0.1)
        for seg in segments_iter:
            out.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
            if progress:
                progress(min(0.99, seg.end / duration),
                         f"识别中 {seg.end:.0f}/{info.duration:.0f} 秒")
    finally:
        if tmp_wav:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass
    info_cfg["duration"] = info.duration
    return out, info.language, info_cfg
