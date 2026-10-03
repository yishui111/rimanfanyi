# -*- coding: utf-8 -*-
"""近似 chrF(字符 n-gram F-score)评分,用于翻译质量自动评测。"""
from collections import Counter


def _ngrams(s, n):
    return Counter(s[i:i + n] for i in range(len(s) - n + 1))


def chrf(ref, hyp, max_n=4, beta=2):
    """返回 0~100,越高越好。与 sacreBLEU 的 chrF 口径近似。"""
    ref, hyp = ref.replace(" ", ""), hyp.replace(" ", "")
    if not ref or not hyp:
        return 0.0
    precs, recs = [], []
    for n in range(1, max_n + 1):
        rg, hg = _ngrams(ref, n), _ngrams(hyp, n)
        overlap = sum((rg & hg).values())
        precs.append(overlap / max(sum(hg.values()), 1))
        recs.append(overlap / max(sum(rg.values()), 1))
    p = sum(precs) / max_n
    r = sum(recs) / max_n
    if p + r == 0:
        return 0.0
    b = beta * beta
    return (1 + b) * p * r / (b * p + r) * 100
