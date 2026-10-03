# -*- coding: utf-8 -*-
"""字幕文件翻译测试:4 种真实场景
1. UTF-8 日语 SRT(含 <i> 标记与多行)
2. Shift-JIS 编码日语 SRT(老生肉常见,考验编码检测)
3. 带样式的韩语 ASS(考验样式与时间轴保留)
4. 日语 VTT(网页视频格式)
结果写入 测试结果/05_字幕文件翻译/
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)

import pysubs2

from subtrans import config, pipeline
from subtrans.subtitles import load as load_subs

OUT = os.path.join(PROJ, "测试结果", "05_字幕文件翻译")


def make_samples():
    os.makedirs(OUT, exist_ok=True)

    srt_utf8 = """1
00:00:01,000 --> 00:00:03,200
<i>アクロスざ・ワールド!</i>

2
00:00:04,000 --> 00:00:06,500
今日からお前は、うちの部室の管理人だ。

3
00:00:07,200 --> 00:00:09,800
えっ、いきなり何言ってるの!?

4
00:00:10,500 --> 00:00:13,000
♪~ dream sorter ~♪
"""
    with open(os.path.join(OUT, "anime_ep01.srt"), "w", encoding="utf-8") as f:
        f.write(srt_utf8)

    srt_sjis = ("1\n00:00:01,000 --> 00:00:03,000\nようこそ、沖縄へ。\n\n"
                "2\n00:00:04,000 --> 00:00:06,000\n今回は精一杯戦うぞ!\n\n")
    with open(os.path.join(OUT, "anime_ep01_shiftjis.srt"), "wb") as f:
        f.write(srt_sjis.encode("shift_jis"))

    subs = pysubs2.SSAFile()
    subs.info["Title"] = "webtoon_ep01"
    subs.styles["Main"] = pysubs2.SSAStyle(fontname="Malgun Gothic", fontsize=42,
                                           primarycolor=pysubs2.Color(255, 255, 120))
    subs.events.append(pysubs2.SSAEvent(start=1000, end=3500,
                                        text="이번 계획은 절대 실패할 리 없어.",
                                        style="Main"))
    subs.events.append(pysubs2.SSAEvent(start=4000, end=6500,
                                        text="Trust me! 뭐든지 해낼 수 있어.",
                                        style="Main"))
    subs.save(os.path.join(OUT, "webtoon_ep01.ass"))

    vtt = ("WEBVTT\n\n"
           "00:01.000 --> 00:03.200\n夜空がきれいだね。\n\n"
           "00:04.000 --> 00:06.000\n流れ星!願いごと、言った?\n\n")
    with open(os.path.join(OUT, "anime_op.vtt"), "w", encoding="utf-8") as f:
        f.write(vtt)


def main():
    make_samples()
    cfg = config.load()
    report = ["# 字幕文件翻译测试", "",
              "覆盖:UTF-8 SRT / Shift-JIS SRT(编码自动检测)/ 带样式 ASS / VTT", ""]

    cases = [
        ("anime_ep01.srt", "日语 SRT(UTF-8,<i>标记)"),
        ("anime_ep01_shiftjis.srt", "日语 SRT(Shift-JIS 编码)"),
        ("webtoon_ep01.ass", "韩语 ASS(带样式)"),
        ("anime_op.vtt", "日语 VTT"),
    ]
    ok = 0
    for name, desc in cases:
        path = os.path.join(OUT, name)
        print(f"翻译 {name} ...")
        try:
            r = pipeline.translate_subtitle(path, cfg, src_lang="auto")
            out_path = r["output"]
            out_subs = pysubs2.load(out_path, encoding="utf-8")
            zh_text = "\n".join(e.plaintext for e in out_subs.events)
            # 时间轴保留检查(源文件用支持编码检测的 loader 读取)
            src_subs = load_subs(path)
            timing_ok = all(
                (a.start, a.end) == (b.start, b.end)
                for a, b in zip(src_subs.events, out_subs.events)
                if a.plaintext.strip() and b.plaintext.strip())
            ok += 1
            report.append(f"## {name}({desc})")
            report.append(f"- 源语言检测:`{r['lang']}`,翻译 {r['lines']} 行,时间轴保留:{'通过' if timing_ok else '失败'}")
            report.append("- 输出内容:")
            report.append("```")
            report.append(zh_text)
            report.append("```\n")
            print(f"  -> {out_path}(语言 {r['lang']},时间轴保留 {timing_ok})")
        except Exception as e:
            report.append(f"## {name}({desc})\n- **失败**: {e}\n")
            print(f"  [失败] {e}")

    report.append(f"\n**结果:{ok}/{len(cases)} 通过**")
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report) + "\n")
    print(f"完成:{ok}/{len(cases)} 通过")


if __name__ == "__main__":
    main()
