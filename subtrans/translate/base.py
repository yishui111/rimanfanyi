"""翻译后端基类。"""


class TranslatorBase:
    name = "base"
    batch_size = 16

    def warmup(self):
        """可选:预加载/预热模型。"""

    def translate_batch(self, lines, src_lang, history=None):
        """把一批字幕行翻译成简体中文。

        lines: list[str]
        src_lang: "ja" | "ko"
        history: 最近的 (原文, 译文) 列表,供有上下文能力的后端参考
        返回: list[str],与 lines 等长
        """
        raise NotImplementedError

    def close(self):
        """释放模型与显存/内存。"""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
