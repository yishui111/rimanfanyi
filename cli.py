"""命令行入口。

用法(.venv\\Scripts\\python.exe -X utf8 cli.py ...):
  info                  查看当前后端与设备
  translate <路径>      翻译视频/字幕文件/整个文件夹
    --lang auto|ja|ko   源语言(默认自动检测)
    --backend auto|nllb|api
    --overwrite         已有 .zh 输出时也重新翻译
  serve                 启动网页界面
"""
import argparse
import os
import sys
import time

from subtrans import config, hf_env, paths, pipeline
from subtrans.translate import detect_backend

hf_env.setup()
paths.ensure_dirs()


class CliProgress:
    def __init__(self, title):
        self.title = title
        self.last = -5

    def __call__(self, frac, desc=""):
        pct = int(frac * 100)
        if pct >= self.last + 5:
            self.last = pct
            print(f"  {self.title} {pct:3d}% {desc}", flush=True)


def iter_files(path):
    if os.path.isfile(path):
        yield path
        return
    for dirpath, _, names in os.walk(path):
        for n in sorted(names):
            ext = os.path.splitext(n)[1].lower()
            if ext in paths.VIDEO_EXTS or ext in paths.SUBTITLE_EXTS:
                if ".zh." in n:
                    continue
                yield os.path.join(dirpath, n)


def translate_cmd(args):
    cfg = config.load()
    if args.backend != "auto":
        cfg["translation_backend"] = args.backend
    if args.lang != "auto":
        cfg["asr"]["language"] = args.lang

    targets = list(iter_files(args.path))
    if not targets:
        print(f"[!] 未找到可处理的视频/字幕文件:{args.path}")
        sys.exit(1)
    print(f"共 {len(targets)} 个文件,后端:{detect_backend(cfg)[0]}")

    ok = fail = skip = 0
    for i, path in enumerate(targets, 1):
        ext = os.path.splitext(path)[1].lower()
        root, _ = os.path.splitext(path)
        zh_exists = os.path.exists(f"{root}.zh.srt") or os.path.exists(f"{root}.zh{ext}")
        if zh_exists and not args.overwrite:
            print(f"[{i}/{len(targets)}] 跳过(已有中文输出):{os.path.basename(path)}")
            skip += 1
            continue
        print(f"[{i}/{len(targets)}] {os.path.basename(path)}")
        t0 = time.time()
        try:
            if ext in paths.VIDEO_EXTS:
                r = pipeline.translate_video(path, cfg, src_lang=args.lang,
                                             progress=CliProgress("进度"))
                print(f"  -> {os.path.basename(r['zh_srt'])} "
                      f"(语言 {r['detected']},{time.time() - t0:.0f} 秒)")
            else:
                r = pipeline.translate_subtitle(path, cfg, src_lang=args.lang,
                                                progress=CliProgress("进度"))
                print(f"  -> {os.path.basename(r['output'])} "
                     f"(语言 {r['lang']},{time.time() - t0:.0f} 秒)")
            ok += 1
        except Exception as e:
            print(f"  [失败] {e}")
            fail += 1
    print(f"\n完成:成功 {ok},跳过 {skip},失败 {fail}")


def warn_non_ascii_root():
    if not paths.is_ascii_root():
        print("[!] 警告:项目路径包含中文/非 ASCII 字符。实测部分安全软件(如火绒)会让"
              "\n    大模型加载时进程被静默终止(无报错)。建议把项目移到纯英文路径,"
              "\n    或执行: mklink /J C:\\subtrans \"%s\" 后从 C:\\subtrans 运行。" % os.getcwd())


def main():
    warn_non_ascii_root()
    ap = argparse.ArgumentParser(description="日漫/韩漫字幕翻译")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap.add_argument("--version", action="store_true")

    p_info = sub.add_parser("info", help="查看当前后端与设备")
    p_tr = sub.add_parser("translate", help="翻译视频/字幕/文件夹")
    p_tr.add_argument("path")
    p_tr.add_argument("--lang", default="auto", choices=["auto", "ja", "ko"])
    p_tr.add_argument("--backend", default="auto", choices=["auto", "nllb", "api"])
    p_tr.add_argument("--overwrite", action="store_true")
    sub.add_parser("serve", help="启动网页界面")

    args = ap.parse_args()
    if args.cmd == "info":
        cfg = config.load()
        mode, why = detect_backend(cfg)
        try:
            import ctranslate2
            gpu = ctranslate2.get_cuda_device_count()
        except Exception:
            gpu = 0
        print(f"翻译后端 : {mode}({why})")
        print(f"NVIDIA GPU: {'可用' if gpu else '不可用(将使用CPU)'}")
        print(f"配置文件 : {paths.CONFIG_FILE}")
    elif args.cmd == "translate":
        translate_cmd(args)
    elif args.cmd == "serve":
        from subtrans import server
        server.main()


if __name__ == "__main__":
    main()
