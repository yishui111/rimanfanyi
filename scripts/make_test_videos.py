# -*- coding: utf-8 -*-
"""合成"日漫/韩漫风格"测试视频:真实 TTS 语音 + 底部字幕渲染。

用途:端到端流水线测试。合成视频的每句台词出现时间已知(写入 ground_truth.json),
可与流水线输出逐句对照,精确计算语音识别准确率(CER)与翻译质量(chrf),
比拿来源不明的片源测试更客观、也可复现。
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

import edge_tts
import pysubs2

GAP = 0.8          # 句间停顿(秒)
LEAD = 0.5         # 开头留白(秒)

JP_LINES = [
    {"text": "ついに来たな、この日が。", "zh": "这一天终于来了。"},
    {"text": "俺の名前は蒼井瞬。ごく普通の高校生だ。", "zh": "我叫苍井瞬,是个普通的高中生。"},
    {"text": "そんなの、絶対におかしいよ!", "zh": "那种事,绝对不对劲!"},
    {"text": "力が、また暴れそうだ。", "zh": "力量好像又要暴走了。"},
    {"text": "大丈夫、私がついてるから。", "zh": "没关系,有我在。"},
    {"text": "諦めたら、そこで試合終了だよ。", "zh": "一旦放弃,比赛就结束了。"},
    {"text": "危ない!下がって!", "zh": "危险!快退后!"},
    {"text": "この街には、まだ知られざる秘密が眠っている。", "zh": "这座城市还沉睡着不为人知的秘密。"},
    {"text": "待って!まだ話があるの!", "zh": "等等!我还有话要说!"},
    {"text": "兄さん、その傷、まさか。", "zh": "哥哥,那个伤……难道说。"},
    {"text": "世界を敵に回しても、守り抜いてみせる。", "zh": "就算与全世界为敌,我也要守护到底。"},
    {"text": "夕日がきれいだね。ずっとこうしてられたらいいのに。", "zh": "夕阳真美啊。要是能一直这样就好了。"},
]

KR_LINES = [
    {"text": "드디어 왔구나, 이 날이.", "zh": "这一天终于来了。"},
    {"text": "내 이름은 김하늘, 평범한 회사원이야.", "zh": "我叫金荷娜,是个普通的上班族。"},
    {"text": "그런 게 말이 돼? 절대 말이 안 돼!", "zh": "那说得通吗?绝对说不通!"},
    {"text": "괜찮아, 내가 옆에 있을게.", "zh": "没关系,我会在你身边。"},
    {"text": "포기하면, 거기서 게임 끝이야.", "zh": "一旦放弃,游戏就结束了。"},
    {"text": "위험해! 물러나!", "zh": "危险!退后!"},
    {"text": "이 도시에는 아직 아무도 모르는 비밀이 잠들어 있어.", "zh": "这座城市还沉睡着无人知晓的秘密。"},
    {"text": "기다려! 아직 할 말이 있어!", "zh": "等等!我还有话要说!"},
    {"text": "오빠, 그 상처, 설마.", "zh": "哥,那个伤……难道。"},
    {"text": "온 세상이 적이 되어도, 끝까지 지켜볼게.", "zh": "就算全世界成为敌人,我也会守护到底。"},
    {"text": "노을이 참 예쁘다. 이대로 계속 있었으면 좋겠어.", "zh": "晚霞真美。真希望就这样一直下去。"},
    {"text": "진짜 강함은 사람을 다치게 하는 게 아니야.", "zh": "真正的强大,不是去伤害别人。"},
]

SPECS = {
    "jp": {"voice": "ja-JP-NanamiNeural", "font": r"C:\Windows\Fonts\YuGothM.ttc",
           "title": "テスト動画(合成音声)", "lang": "ja", "lines": JP_LINES},
    "kr": {"voice": "ko-KR-SunHiNeural", "font": r"C:\Windows\Fonts\malgun.ttf",
           "title": "테스트 동영상(TTS)", "lang": "ko", "lines": KR_LINES},
}


def _ffmpeg_path(p):
    """drawtext 选项值里的 Windows 路径需要转义盘符冒号。"""
    return p.replace("\\", "/").replace(":", r"\:")


def ffprobe_duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", path])
    return float(json.loads(out)["format"]["duration"])


async def tts(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["jp", "kr"], required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = SPECS[args.lang]
    os.makedirs(args.out, exist_ok=True)

    # 1) 逐句生成 TTS 语音
    mp3s = []
    for i, line in enumerate(spec["lines"]):
        p = os.path.abspath(os.path.join(args.out, f"line_{i:02d}.mp3"))
        print(f"TTS {i + 1}/{len(spec['lines'])}: {line['text']}")
        asyncio.run(tts(line["text"], spec["voice"], p))
        mp3s.append(p)
        time.sleep(0.3)

    durs = [ffprobe_duration(p) for p in mp3s]
    starts, t = [], LEAD
    for d in durs:
        starts.append(t)
        t += d + GAP
    total = t + 0.5

    # 2) 拼接音频(句间补静音)
    inputs, filters, refs = [], [], []
    for i, p in enumerate(mp3s):
        inputs += ["-i", p]
        filters.append(f"[{i}:a]apad=pad_dur={GAP},"
                       f"aformat=sample_rates=44100:channel_layouts=mono[a{i}]")
        refs.append(f"[a{i}]")
    filters.append("".join(refs) + f"concat=n={len(mp3s)}:v=0:a=1[aout]")
    audio = os.path.abspath(os.path.join(args.out, "audio.m4a"))
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", *inputs,
                           "-filter_complex", ";".join(filters),
                           "-map", "[aout]", "-c:a", "aac", audio])

    # 3) 渲染视频:深色背景 + 片名 + 逐句底部字幕(模拟硬字幕)
    font = _ffmpeg_path(spec["font"])
    vf = [f"drawtext=fontfile='{font}':text='{spec['title']}':"
          f"fontsize=32:fontcolor=0x90A4AE:x=(w-text_w)/2:y=56"]
    for i, line in enumerate(spec["lines"]):
        tf = os.path.abspath(os.path.join(args.out, f"txt_{i:02d}.txt"))
        with open(tf, "w", encoding="utf-8") as f:
            f.write(line["text"])
        s, e = starts[i], starts[i] + durs[i] + 0.4
        vf.append(f"drawtext=fontfile='{font}':textfile='{_ffmpeg_path(tf)}':"
                  f"fontsize=44:fontcolor=white:borderw=3:bordercolor=black@0.9:"
                  f"x=(w-text_w)/2:y=h-150:enable='between(t,{s:.2f},{e:.2f})'")
    video = os.path.abspath(os.path.join(args.out, f"test_{args.lang}.mp4"))
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error",
                           "-f", "lavfi", "-i",
                           f"color=c=0x101820:s=1280x720:r=24:d={total:.2f}",
                           "-i", audio,
                           "-vf", ",".join(vf),
                           "-map", "0:v", "-map", "1:a",
                           "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                           "-c:a", "copy", "-shortest", video])

    # 4) 写真值文件(源语言 SRT + JSON 元数据)
    srt = pysubs2.SSAFile()
    meta = {"lang": spec["lang"], "duration": total, "lines": []}
    for i, line in enumerate(spec["lines"]):
        st, en = int(starts[i] * 1000), int((starts[i] + durs[i]) * 1000)
        srt.events.append(pysubs2.SSAEvent(start=st, end=en, text=line["text"]))
        meta["lines"].append({"text": line["text"], "zh": line["zh"],
                              "start": starts[i], "end": starts[i] + durs[i]})
    srt.save(os.path.join(args.out, f"ground_truth_{args.lang}.srt"))
    with open(os.path.join(args.out, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    for p in mp3s + [audio]:
        os.remove(p)
    print(f"完成:{video}(时长 {total:.1f} 秒,{len(spec['lines'])} 句)")


if __name__ == "__main__":
    main()
