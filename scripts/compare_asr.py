# -*- coding: utf-8 -*-
"""语音识别输出 vs 合成视频真值:全局 CER + 逐句召回 + 时间轴对照。"""
import json

import jiwer
import pysubs2

_PUNCT = "、。!,.??:;「」『』()()《》~〜-…·,.'\"“”"


def norm(s):
    for ch in _PUNCT:
        s = s.replace(ch, "")
    return "".join(s.split())


def load_srt_events(path):
    subs = pysubs2.load(path, encoding="utf-8")
    return [(e.start / 1000, e.end / 1000, e.plaintext.strip())
            for e in subs.events if e.plaintext.strip()]


def align(gt_lines, asr_events):
    """按时间重叠把 ASR 片段归到真值句。"""
    rows = []
    for line in gt_lines:
        gs, ge = line["start"], line["end"]
        cands = [t for s, e, t in asr_events
                 if min(e, ge) - max(s, gs) > 0.3 * (ge - gs)]
        rows.append((line["text"], " ".join(cands)))
    return rows


def evaluate(gt_json, asr_srt):
    """全局 CER + ASR 分段明细。

    whisper 会把相邻句子合并成段,逐句 1:1 对齐不成立,
    因此公平口径是:全部真值文本 vs 全部识别文本的全局字错率。
    """
    with open(gt_json, encoding="utf-8") as f:
        meta = json.load(f)
    events = load_srt_events(asr_srt)

    refs = norm("".join(l["text"] for l in meta["lines"]))
    hyps = norm("".join(t for _, _, t in events))
    cer = jiwer.cer(refs, hyps) if refs else 1.0

    # 每条 ASR 段落落到哪个真值句(按段落中点,只归属一次)
    rows = []
    for s, e, t in events:
        mid = (s + e) / 2
        owners = [l["text"] for l in meta["lines"]
                  if l["start"] - 0.3 <= mid <= l["end"] + 0.8]
        rows.append((s, e, t, " + ".join(owners) or "(无对应)"))
    return {"cer": cer, "segments": len(events),
            "gt_lines": len(meta["lines"]), "rows": rows}


def to_markdown(result, title):
    lines = [f"## {title}", "",
             f"- 全局字错率 CER:**{result['cer'] * 100:.1f}%**(越低越好;"
             f"whisper 会把相邻短句合并成段,故按全文对照计算)",
             f"- ASR 输出 {result['segments']} 段(真值 {result['gt_lines']} 句)", "",
             "| 时间 | ASR 识别结果 | 对应真值句 |",
             "|------|------------|-----------|"]
    for s, e, t, owner in result["rows"]:
        lines.append(f"| {s:6.1f}-{e:6.1f}s | {t} | {owner} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys
    res = evaluate(sys.argv[1], sys.argv[2])
    print(to_markdown(res, "ASR 评测"))
