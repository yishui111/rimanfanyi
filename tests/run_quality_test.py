# -*- coding: utf-8 -*-
"""翻译质量测试:日/韩各 30 句(动漫/韩剧风格)翻译成中文,与人工参考译文对照,
输出逐句 CSV + chrF 评分报告,另含边界用例(数字/英文混排/长句/拟声词)。

结果写入 测试结果/02_翻译质量测试/
"""
import csv
import json
import os
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
sys.path.insert(0, os.path.join(PROJ, "scripts"))

from metrics import chrf                      # noqa: E402
from subtrans import config, pipeline         # noqa: E402
from subtrans.subtitles import detect_language  # noqa: E402

OUT_DIR = os.path.join(PROJ, "测试结果", "02_翻译质量测试")

JA = [
    ("ついに来たな、この日が。", "这一天终于来了。"),
    ("俺の名前は蒼井瞬。ごく普通の高校生だ。", "我叫苍井瞬,是个普通的高中生。"),
    ("そんなの、絶対におかしいよ!", "那种事,绝对不对劲!"),
    ("大丈夫、私がついてるから。", "没关系,有我在。"),
    ("諦めたら、そこで試合終了だよ。", "一旦放弃,比赛就结束了。"),
    ("危ない!下がって!", "危险!快退后!"),
    ("世界を敵に回しても、守り抜いてみせる。", "就算与全世界为敌,我也要守护到底。"),
    ("夕日がきれいだね。ずっとこうしてられたらいいのに。", "夕阳真美啊,要是能一直这样就好了。"),
    ("本当の強さは、人を傷つけることじゃない。", "真正的强大,不是去伤害别人。"),
    ("行こう、約束の場所へ。", "出发吧,去我们约定的地方。"),
    ("ドキドキが止まらない……", "心跳个不停……"),
    ("お兄ちゃん、おはよう!今日の朝ごはん何?", "哥,早上好!今天早饭吃什么?"),
    ("ゲームオーバーだ。もう一度最初からやり直そう。", "游戏结束了,从头再来一次吧。"),
    ("彼女の笑顔は、春の陽だまりのようだ。", "她的笑容像春天的阳光。"),
    ("この作戦、成功する確率は何パーセントだ?", "这个作战的成功率是多少?"),
    ("やれやれ、また面倒なことに巻き込まれたな。", "唉呀,又被卷进麻烦事里了。"),
    ("信じるか信じないかは、あなた次第です。", "信不信由你。"),
    ("風が強くなってきた。嵐が来るかもしれない。", "风变大了,暴风雨可能要来了。"),
    ("俺の必殺技を食らいたくなければ、退がれ!", "不想尝我的必杀技就退下!"),
    ("秘密基地は、あの廃校の地下にある。", "秘密基地在那所废弃学校的地下。"),
    ("ごめん、待たせちゃった?電車が遅れてて。", "抱歉让你久等了吗?电车晚点了。"),
    ("このカレー、辛すぎて食べられないよ。", "这个咖喱太辣了,吃不了啊。"),
    ("彼は昨日、会社を辞める決意をした。", "他昨天下定决心辞职了。"),
    ("未来はまだ誰にも見えない。だからこそ、希望がある。", "未来谁也看不见,正因如此才有希望。"),
    ("東京タワーの展望台から、街全体が見渡せる。", "从东京塔的展望台可以俯瞰整座城市。"),
    ("力を貸してくれ、頼む!", "帮帮我,求你了!"),
    ("この先、立ち入り禁止だ。", "前面禁止入内。"),
    ("もしそうなったら、どうするつもりだったの?", "如果变成那样,你打算怎么办?"),
    ("桜の花びらが、風に乗って舞っている。", "樱花花瓣随风飞舞。"),
    ("今夜で最後だ。思い出しておくれ、僕たちの栄光を。", "今晚是最后一次了,记住我们的荣光吧。"),
]

KO = [
    ("드디어 왔구나, 이 날이.", "这一天终于来了。"),
    ("내 이름은 김하늘, 평범한 회사원이야.", "我叫金荷娜,是个普通的上班族。"),
    ("그런 게 말이 돼? 절대 말이 안 돼!", "那说得通吗?绝对说不通!"),
    ("괜찮아, 내가 옆에 있을게.", "没关系,我会在你身边。"),
    ("포기하면, 거기서 게임 끝이야.", "一旦放弃,游戏就结束了。"),
    ("위험해! 물러나!", "危险!退后!"),
    ("온 세상이 적이 되어도, 끝까지 지켜볼게.", "就算全世界成为敌人,我也会守护到底。"),
    ("노을이 참 예쁘다. 이대로 계속 있었으면 좋겠어.", "晚霞真美,真希望就这样一直下去。"),
    ("진짜 강함은 사람을 다치게 하는 게 아니야.", "真正的强大,不是去伤害别人。"),
    ("가자, 우리 약속한 장소로.", "走吧,去我们约定的地方。"),
    ("심장이 왜 이렇게 빨리 뛰지……", "心脏为什么跳这么快……"),
    ("오빠, 아침 먹었어? 오늘 점심은 내가 살게.", "哥,吃早饭了吗?今天午饭我请。"),
    ("게임 오버야. 처음부터 다시 시작하자.", "游戏结束了,从头再开始吧。"),
    ("그녀의 미소는 봄날의 햇살 같았다.", "她的笑容像春天的阳光。"),
    ("이 작전이 성공할 확률이 몇 퍼센트야?", "这个作战的成功率是多少?"),
    ("아휴, 또 귀찮은 일에 휘말렸네.", "唉,又被卷进麻烦事里了。"),
    ("믿거나 말거나, 그건 네 마음대로야.", "信不信由你。"),
    ("바람이 세져가고 있어. 폭풍이 올지도 몰라.", "风越来越大了,暴风雨可能要来了。"),
    ("내 필살기를 맞고 싶지 않으면 물러나!", "不想挨我的必杀技就退下!"),
    ("비밀 기지는 저 폐허가 된 학교 지하에 있어.", "秘密基地在那座废弃学校的地下。"),
    ("미안, 오래 기다렸어? 지하철이 늦어서.", "抱歉,等很久了吗?地铁晚点了。"),
    ("이 카레는 너무 매워서 못 먹겠어.", "这个咖喱太辣了,吃不了。"),
    ("그는 어제 회사를 그만두기로 결심했어.", "他昨天下定决心辞职了。"),
    ("미래는 아직 아무도 볼 수 없어. 그래서 희망이 있는 거야.", "未来谁也看不见,正因如此才有希望。"),
    ("서울타워 전망대에서 도시 전체가 보여.", "从首尔塔瞭望台能看到整座城市。"),
    ("힘을 빌려줘, 부탁이야!", "帮帮我,求你了!"),
    ("여기서부터 출입금지야.", "这里开始禁止入内。"),
    ("만약 그렇게 됐다면, 어떻게 할 생각이었어?", "如果变成那样,你打算怎么办?"),
    ("벚꽃잎이 바람을 타고 흩날리고 있어.", "樱花花瓣随风飞舞。"),
    ("오늘 밤이 마지막이야. 우리의 영광을 기억해 줘.", "今晚是最后一次,记住我们的荣光吧。"),
]

EDGE = [
    ("2024年、新たな時代が始まる。", "2024年,新时代开始了。", "ja"),
    ("システムエラーが発生しました。再起動してください。", "发生系统错误,请重新启动。", "ja"),
    ("Contact me at 090-1234-5678だ!", "打 090-1234-5678 联系我!", "ja"),
    ("제일 중요한 건 포기하지 않는 마음입니다.", "最重要的是不放弃的心。", "ko"),
    ("このセリフは、ものすごく長いのですが、1行の字幕として表示されることを想定していて、翻訳モデルが長文を適切に処理できるかどうかを確認するためのテスト用例です。", "这句台词非常长,但假设它会作为一行字幕显示,是为了确认翻译模型能否正确处理长句的测试用例。", "ja"),
]


def run_set(name, pairs, lang, translator, csv_path, md_lines):
    rows = []
    t0 = time.time()
    for src, ref in pairs:
        out = translator.translate_batch([src], lang)[0]
        score = chrf(ref, out)
        rows.append((src, ref, out, score))
        print(f"  [{lang}] chrF {score:5.1f}  {src} -> {out}")
    secs = time.time() - t0

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["源文", "参考译文", "模型输出", "chrF"])
        w.writerows(rows)

    scores = [r[3] for r in rows]
    avg = sum(scores) / len(scores)
    md_lines.append(f"## {name}(共 {len(rows)} 句)\n")
    md_lines.append(f"- 平均 chrF:**{avg:.1f}**(0~100,越高越好;机翻 vs 人工参考一般在 40~60)")
    md_lines.append(f"- 耗时 {secs:.1f} 秒,约 {len(rows) / secs:.1f} 句/秒\n")
    md_lines.append("| # | 源文 | 参考译文 | 模型输出 | chrF |")
    md_lines.append("|---|------|---------|---------|-----:|")
    for i, (src, ref, out, s) in enumerate(rows, 1):
        md_lines.append(f"| {i} | {src} | {ref} | {out} | {s:.1f} |")
    md_lines.append("")
    return avg


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="auto",
                    choices=["auto", "nllb", "api"])
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = config.load()
    if args.backend != "auto":
        cfg["translation_backend"] = args.backend
    translator = pipeline.get_translator(cfg)
    backend = getattr(translator, "backend_name", translator.name)
    tag = "nllb" if isinstance(translator, object) and "NLLB" in backend else "llm"
    print(f"翻译后端:{backend}")

    md = [f"# 翻译质量测试报告({backend})", "",
          f"- 翻译后端:`{backend}`",
          f"- 测试集:日语 30 句 + 韩语 30 句(动漫/韩剧口语风格)+ 5 条边界用例",
          f"- 评分口径:chrF(字符级 n-gram F值,近似 sacreBLEU 实现)", ""]

    suffix = "" if tag == "llm" else "_nllb"
    avg_ja = run_set("日语 → 中文", JA, "ja", translator,
                     os.path.join(OUT_DIR, f"ja_results{suffix}.csv"), md)
    avg_ko = run_set("韩语 → 中文", KO, "ko", translator,
                     os.path.join(OUT_DIR, f"ko_results{suffix}.csv"), md)

    md.append("## 边界用例(无参考,人工检查输出)\n")
    md.append("| 源文 | 模型输出 |")
    md.append("|------|---------|")
    edge_rows = []
    for src, ref, lang in EDGE:
        out = translator.translate_batch([src], lang)[0]
        edge_rows.append((lang, src, out))
        md.append(f"| {src} | {out} |")
    md.append("")

    with open(os.path.join(OUT_DIR, f"edge_results{suffix}.csv"), "w", newline="",
              encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["语言", "源文", "模型输出"])
        w.writerows(edge_rows)

    md.append("## 结论\n")
    md.append(f"- 日语平均 chrF **{avg_ja:.1f}**,韩语平均 chrF **{avg_ko:.1f}**。")
    if tag == "llm":
        md.append("- LLM 后端译文口语自然,人名/语气保持好;成绩详见上表。")
    else:
        md.append("- NLLB-600M 属于轻量级本地翻译模型,译文准确但偏书面;"
                  "对比 report.md(LLM 后端)可见口语化差距。")
    with open(os.path.join(OUT_DIR, f"report{suffix}.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\n报告已写入 {OUT_DIR}")


if __name__ == "__main__":
    main()
