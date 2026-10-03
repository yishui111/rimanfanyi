# -*- coding: utf-8 -*-
"""端到端测试:对合成测试视频(真值已知)跑完整流水线:
视频 -> whisper 语音识别 -> 翻译 -> 中文字幕,并输出评测报告。

用法:python run_e2e.py <测试视频所在目录>(目录内需有 ground_truth.json)
结果写在同目录 report_asr.md / report_translation.md / report.md
"""
import json
import os
import subprocess
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
sys.path.insert(0, os.path.join(PROJ, "scripts"))

import compare_asr                        # noqa: E402
from metrics import chrf                  # noqa: E402
from subtrans import config, pipeline     # noqa: E402


def vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True)
        return int(out.strip().splitlines()[0])
    except Exception:
        return -1


def align_zh(gt_lines, zh_srt):
    """中点归属:每条中文字幕段只归到一句真值(whisper 段可能跨句)。"""
    events = compare_asr.load_srt_events(zh_srt)
    rows = []
    for s, e, t in events:
        mid = (s + e) / 2
        owners = [l for l in gt_lines
                  if l["start"] - 0.3 <= mid <= l["end"] + 0.8]
        rows.append((t, owners))
    return rows


def main(video_dir):
    gt_json = os.path.join(video_dir, "ground_truth.json")
    with open(gt_json, encoding="utf-8") as f:
        meta = json.load(f)
    video = None
    for n in os.listdir(video_dir):
        if n.startswith("test_") and n.endswith(".mp4"):
            video = os.path.join(video_dir, n)
    assert video, "找不到测试视频"

    cfg = config.load()
    backend = None
    vram0 = vram_mb()
    t0 = time.time()
    r = pipeline.translate_video(video, cfg, src_lang="auto", keep_source=True)
    elapsed = time.time() - t0

    src_srt, zh_srt = r["src_srt"], r["zh_srt"]
    lang_name = "日语" if meta["lang"] == "ja" else "韩语"

    # --- ASR 评测 ---
    asr_res = compare_asr.evaluate(gt_json, src_srt)
    with open(os.path.join(video_dir, "report_asr.md"), "w", encoding="utf-8") as f:
        f.write(compare_asr.to_markdown(asr_res, f"{lang_name}语音识别评测(whisper)"))

    # --- 翻译评测:每段译文对照其覆盖的真值参考(拼接),另算全局 chrF ---
    rows = align_zh(meta["lines"], zh_srt)
    scored = []
    for t, owners in rows:
        ref = "".join(o["zh"] for o in owners)
        if ref:
            scored.append((ref, t, chrf(ref, t)))
    avg = sum(s for _, _, s in scored) / max(len(scored), 1)
    gt_all = "".join(l["zh"] for l in meta["lines"])
    zh_all = "".join(t for t, _ in rows)
    chrf_global = chrf(gt_all, zh_all)
    md = [f"# {lang_name}翻译评测", "",
          f"- 全局 chrF:**{chrf_global:.1f}**(全部参考 vs 全部译文,0~100)",
          f"- 分段对照平均 chrF:{avg:.1f}(whisper 合并段对照多句参考,偏低是正常现象)", "",
          "| 流水线译文 | 对应原意(参考) | chrF |", "|-----------|--------------|-----:|"]
    for hyp, owners in rows:
        ref = " + ".join(o["zh"] for o in owners) or "(无对应)"
        s = chrf("".join(o["zh"] for o in owners), hyp) if owners else 0.0
        md.append(f"| {hyp} | {ref} | {s:.1f} |")
    with open(os.path.join(video_dir, "report_translation.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # --- 总报告 ---
    rt = elapsed / max(meta["duration"], 1)
    vram1 = vram_mb()
    tm = r.get("timings", {})
    md = [f"# 端到端测试:{os.path.basename(video)}", "",
          f"- 视频:{meta['duration']:.0f} 秒 / {len(meta['lines'])} 句 {lang_name}语音",
          f"- 流水线:语音识别({r['asr']['model']}, {r['asr']['device']}) -> "
          f"翻译 -> 中文字幕",
          f"- 总耗时:{elapsed:.0f} 秒(**{rt:.1f}x 实时**;"
          f"其中识别 {tm.get('asr', 0):.0f}s + 翻译 {tm.get('translate', 0):.0f}s,"
          f"首次运行含模型加载)",
          f"- ASR 全局字错率 CER:{asr_res['cer'] * 100:.1f}%(识别 {asr_res['segments']} 段)",
          f"- 翻译全局 chrF:{chrf_global:.1f}",
          f"- 显存:{vram0}MB -> {vram1}MB",
          f"- 输出:`{os.path.basename(src_srt)}`(原语言) + `{os.path.basename(zh_srt)}`(中文)", "",
          "详见 report_asr.md / report_translation.md"]
    with open(os.path.join(video_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main(sys.argv[1])
