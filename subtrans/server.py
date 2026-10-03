"""Gradio 网页界面。启动方式:双击 启动.bat,或
.venv\\Scripts\\python.exe -X utf8 -m subtrans.server
"""
import atexit
import logging
import os
import socket
import sys
import threading

from . import config, hf_env, paths, pipeline
from .translate import detect_backend

hf_env.setup()
paths.ensure_dirs()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(paths.LOG_FILE, encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("server")


def port_in_use(port):
    s = socket.socket()
    s.settimeout(1)
    try:
        s.bind(("127.0.0.1", port))
        return False
    except OSError:
        return True
    finally:
        s.close()


def _preload(cfg):
    try:
        tr = pipeline.get_translator(cfg)
        tr.warmup()
        logger.info("翻译后端预热完成:%s", getattr(tr, "backend_name", tr.name))
    except Exception as e:
        logger.error("翻译后端预热失败(首次翻译时会重试): %s", e)
    try:
        from . import asr as asr_mod
        _, info = asr_mod.load_model(cfg["asr"])
        logger.info("语音识别模型预热完成:%s(%s)", info["model"], info["device"])
    except Exception as e:
        logger.error("语音识别模型预热失败(首次翻译时会重试): %s", e)


def _preview(srt_path, max_lines=60):
    with open(srt_path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().splitlines()
    head = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        head += f"\n...(共 {len(lines)} 行,已省略)"
    return head


def build_ui(cfg):
    import gradio as gr

    backend_mode, backend_why = detect_backend(cfg)
    backend_desc = backend_why

    def run_video(video, lang, keep, progress=gr.Progress()):
        if not video:
            raise gr.Error("请先上传视频文件")
        p = pipeline.translate_video(
            video, cfg, src_lang=lang, keep_source=keep,
            progress=lambda f, d: progress(f, desc=d))
        info = (f"**完成!** 检测语言:`{p['detected']}` | 台词行数:{p['lines']}"
                f" | 识别模型:{p['asr']['model']}({p['asr']['device']})\n\n"
                f"中文字幕已保存到视频同目录:`{os.path.basename(p['zh_srt'])}`")
        return p["zh_srt"], _preview(p["zh_srt"]), info

    def run_sub(file, lang, progress=gr.Progress()):
        if not file:
            raise gr.Error("请先上传字幕文件")
        p = pipeline.translate_subtitle(
            file, cfg, src_lang=lang, progress=lambda f, d: progress(f, desc=d))
        info = (f"**完成!** 检测语言:`{p['lang']}` | 翻译行数:{p['lines']}\n\n"
                f"输出文件:`{os.path.basename(p['output'])}`(原格式保留)")
        return p["output"], _preview(p["output"]), info

    about = f"""
## 当前配置
- 翻译后端:**{backend_mode}**({backend_desc})
- 语音识别:whisper `{cfg['asr']['model_size']}`(auto = 有显卡用 large-v3)
- 想换更强的翻译大模型?编辑项目目录下 `config.json`,在 `api` 里填任意 OpenAI 兼容接口
  (DeepSeek / GLM / 本地 Ollama 等),重启即可。

## 使用说明
- 视频翻译:上传生肉视频 → 自动语音识别 → 翻译 → 在视频同目录生成 `xxx.zh.srt`
- 字幕翻译:已有日/韩字幕文件(srt/ass/vtt)直接上传,格式与时间轴原样保留
- 批量处理:命令行 `cli.py translate 文件夹`

## 版权提醒
本工具仅用于**个人观看与学习**。未经授权翻译并公开传播版权作品字幕/视频属于侵权行为。
"""
    with gr.Blocks(title="日漫/韩漫字幕翻译") as demo:
        gr.Markdown("# 🎬 日漫/韩漫字幕翻译\n日文/韩文视频或字幕 → 中文字幕(本地运行)")
        with gr.Tab("视频 → 中文字幕"):
            with gr.Row():
                with gr.Column():
                    video_in = gr.Video(label="上传视频(mp4/mkv/avi...)", sources=["upload"])
                    lang1 = gr.Radio([("自动检测", "auto"), ("日语", "ja"), ("韩语", "ko")],
                                     value="auto", label="源语言")
                    keep = gr.Checkbox(value=True, label="同时保留原语言 SRT(便于校对)")
                    btn1 = gr.Button("开始翻译", variant="primary")
                with gr.Column():
                    out1 = gr.File(label="下载中文字幕")
                    prev1 = gr.Textbox(label="字幕预览", lines=14)
                    info1 = gr.Markdown()
        with gr.Tab("字幕文件 → 中文"):
            with gr.Row():
                with gr.Column():
                    sub_in = gr.File(label="上传字幕(srt/ass/vtt)",
                                     file_types=[".srt", ".ass", ".ssa", ".vtt"])
                    lang2 = gr.Radio([("自动检测", "auto"), ("日语", "ja"), ("韩语", "ko")],
                                     value="auto", label="源语言")
                    btn2 = gr.Button("开始翻译", variant="primary")
                with gr.Column():
                    out2 = gr.File(label="下载中文字幕")
                    prev2 = gr.Textbox(label="字幕预览", lines=14)
                    info2 = gr.Markdown()
        with gr.Tab("关于 / 设置"):
            gr.Markdown(about)
        btn1.click(run_video, [video_in, lang1, keep], [out1, prev1, info1])
        btn2.click(run_sub, [sub_in, lang2], [out2, prev2, info2])
    return demo


def main():
    if not paths.is_ascii_root():
        logger.warning("项目路径包含中文/非 ASCII 字符,部分安全软件(如火绒)会让大模型"
                       "加载时进程被静默终止(无报错)。建议移到纯英文路径,或建目录联接后"
                       "从英文路径启动。")
    cfg = config.load()
    port = int(cfg["server"]["port"])
    if port_in_use(port):
        print(f"[!] 端口 {port} 已被占用,服务可能已在运行。"
              f"请先双击 关闭.bat,再重新启动。")
        sys.exit(2)

    with open(paths.PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.path.exists(paths.PID_FILE) and os.remove(paths.PID_FILE))

    logger.info("服务启动:http://%s:%s(PID %d)",
                cfg["server"]["host"], port, os.getpid())
    if cfg["server"].get("preload"):
        threading.Thread(target=_preload, args=(cfg,), daemon=True).start()

    demo = build_ui(cfg)
    demo.queue().launch(
        server_name=cfg["server"]["host"],
        server_port=port,
        inbrowser=not os.environ.get("SUBTRANS_NO_BROWSER"),
        show_error=True,
    )


if __name__ == "__main__":
    main()
