# -*- coding: utf-8 -*-
"""批量处理测试:用真实 CLI(cli.py translate 文件夹)递归处理混放文件,
并验证二次运行时"已有输出的文件自动跳过"。
结果写入 测试结果/06_批量处理/
"""
import os
import shutil
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(PROJ, "测试结果", "06_批量处理")
INPUT = os.path.join(OUT, "input")

PY = os.path.join(PROJ, ".venv", "Scripts", "python.exe")


def make_inputs():
    os.makedirs(INPUT, exist_ok=True)
    ja = ("1\n00:00:01,000 --> 00:00:02,500\n作戦開始は明日の朝六時だ。\n\n"
          "2\n00:00:03,000 --> 00:00:05,000\n遅れたら、置いていくからな!\n\n")
    with open(os.path.join(INPUT, "ep01_ja.srt"), "w", encoding="utf-8") as f:
        f.write(ja)
    sub = os.path.join(INPUT, "sub")          # 子目录,验证递归
    os.makedirs(sub, exist_ok=True)
    ko = ("1\n00:00:01,000 --> 00:00:03,000\n내일 아침 여섯 시에 작전을 시작한다.\n\n")
    with open(os.path.join(sub, "ep02_ko.srt"), "w", encoding="utf-8") as f:
        f.write(ko)
    with open(os.path.join(INPUT, "readme.txt"), "w", encoding="utf-8") as f:
        f.write("非字幕文件,应被忽略")


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    make_inputs()

    log = []
    cmd = [PY, "-X", "utf8", "cli.py", "translate", INPUT]
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=PROJ, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    log.append("$ cli.py translate 测试结果/06_批量处理/input")
    log.append(r.stdout + (r.stderr or ""))
    first = r.stdout

    # 第二次运行:全部应跳过
    r2 = subprocess.run(cmd, cwd=PROJ, capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    log.append("\n$ 第二次运行(应全部跳过)")
    log.append(r2.stdout + (r2.stderr or ""))

    outputs = []
    for dirpath, _, names in os.walk(INPUT):
        for n in names:
            outputs.append(os.path.relpath(os.path.join(dirpath, n), INPUT))

    skip_ok = "跳过" in r2.stdout and "跳过 2" in r2.stdout
    zh1 = open(os.path.join(INPUT, "ep01_ja.zh.srt"), encoding="utf-8").read()
    zh2 = open(os.path.join(INPUT, "sub", "ep02_ko.zh.srt"), encoding="utf-8").read()

    md = ["# 批量处理测试(cli.py translate 文件夹)", "",
          "```", *log, "```", "",
          f"- 生成文件:{outputs}",
          f"- 子目录递归:{'通过' if 'sub' in ' '.join(outputs) else '失败'}",
          f"- txt 文件忽略:{'通过' if 'readme.txt' in outputs and len(outputs) == 5 else '失败'}",
          f"- 二次运行跳过:{'通过' if skip_ok else '失败'}",
          "", "## 输出内容抽查", "```", zh1, "```", "```", zh2, "```"]
    with open(os.path.join(OUT, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(md[-7:-3])


if __name__ == "__main__":
    main()
