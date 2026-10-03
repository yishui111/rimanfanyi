"""字幕文件读写(SRT/ASS/SSA/VTT)与可翻译行判定。"""
import io
import re

import charset_normalizer
import pysubs2
from pysubs2.exceptions import FormatAutodetectionError

# 含有 日文假名/汉字/谚文 的行才值得翻译;纯数字、纯符号、纯拉丁字母原样保留
_CJK_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]")
_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_HANGUL_RE = re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]")
_HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# gb18030 几乎能解任何字节串,放最后兜底,避免把 Shift-JIS/EUC-KR 解成乱码
_ENCODINGS = ("utf-8-sig", "utf-8", "shift_jis", "cp949", "big5", "gb18030")


def _clean(text):
    """去掉 HTML 标记(<i>)与 ASS 特效标记({\an8}),压平换行。"""
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\{[^}]*\}", "", text)
    return " ".join(text.split()).strip()


def is_translatable(text):
    return bool(text) and bool(_CJK_RE.search(text))


def detect_language(lines):
    """按假名/谚文出现次数判断源语言;仅汉字时默认按日语处理。"""
    kana = sum(len(_KANA_RE.findall(l)) for l in lines)
    hangul = sum(len(_HANGUL_RE.findall(l)) for l in lines)
    if hangul > 0 and hangul * 3 >= kana:
        return "ko"
    return "ja"


def load(path):
    """读取字幕:先做字符集自动检测(UTF-8/Shift-JIS/EUC-KR/GBK/Big5),再逐个尝试。"""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise ValueError(f"无法读取字幕文件 {path}: {e}")
    if not raw.strip():
        return pysubs2.SSAFile()

    candidates = []
    guess = charset_normalizer.from_bytes(raw).best()
    if guess is not None and guess.encoding:
        candidates.append(guess.encoding)
    candidates += [e for e in _ENCODINGS if e not in candidates]

    last_err = None
    for enc in candidates:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError, ValueError) as e:
            last_err = e
            continue
        try:
            return pysubs2.SSAFile.from_string(
                text.replace("\r\n", "\n").replace("\r", "\n"))
        except FormatAutodetectionError as e:
            last_err = e
    raise ValueError(f"无法解码字幕文件 {path}: {last_err}")


def collect_events(subs):
    """返回需要翻译的事件及其清洗后文本,[(event, src_text), ...]。"""
    out = []
    for ev in subs.events:
        text = _clean(ev.plaintext)
        if is_translatable(text):
            out.append((ev, text))
    return out


def translate_events(subs, translator, src_lang="auto", progress=None):
    """就地翻译字幕文本,时间轴与样式保持不变。

    返回 (实际使用的源语言, 翻译行数)。
    """
    items = collect_events(subs)
    if src_lang in ("auto", "", None):
        src_lang = detect_language([t for _, t in items]) if items else "ja"

    # 重复台词只翻一次
    unique = list(dict.fromkeys(t for _, t in items))
    batch = int(getattr(translator, "batch_size", 16) or 16)
    cache = {}

    done = 0
    for i in range(0, len(unique), batch):
        chunk = unique[i:i + batch]
        results = translator.translate_batch(chunk, src_lang)
        for src, dst in zip(chunk, results):
            dst = (dst or "").strip().replace("\n", " ")
            cache[src] = dst if dst else src
        done += len(chunk)
        if progress:
            progress(done / max(1, len(unique)), f"已翻译 {done}/{len(unique)} 行")

    for ev, text in items:
        ev.text = cache.get(text, text)  # 整行替换,输出单行纯文本,兼容所有格式
    return src_lang, len(items)
