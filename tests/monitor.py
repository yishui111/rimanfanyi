# -*- coding: utf-8 -*-
"""记录某一时刻的资源快照(本项目 python 进程 / 全部python / 显存)。"""
import json
import subprocess

import psutil


def vram_mb():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True)
        return int(out.strip().splitlines()[0])
    except Exception:
        return -1


def project_pythons():
    """找出本项目相关的 python 进程(venv 启动器 + 真实解释器子进程)。"""
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
        try:
            name = (p.info["name"] or "").lower()
            if not name.startswith("python"):
                continue
            cl = " ".join(p.info["cmdline"] or [])
            if "subtrans" in cl or ".venv" in cl:
                out.append({"pid": p.info["pid"],
                            "rss_mb": round(p.info["memory_info"].rss / 1e6, 1),
                            "cmd": cl[:150]})
        except Exception:
            pass
    return out


def snapshot(label, path):
    data = {"label": label, "vram_mb": vram_mb(), "procs": project_pythons()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(label, "->", json.dumps(data, ensure_ascii=False))
    return data


if __name__ == "__main__":
    import sys
    snapshot(sys.argv[1], sys.argv[2])
