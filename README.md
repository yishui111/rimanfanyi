# 日漫/韩漫字幕翻译工具

把日文/韩文**视频或字幕文件**翻译成中文,本地运行,不依赖任何在线翻译服务。

> ⚠️ **版权提醒**:本工具仅用于个人观看与学习。未经授权翻译并公开传播版权作品的字幕/视频属于侵权行为,请勿用于发布、传播。

## 工作原理

```
视频文件 ──► faster-whisper 语音识别(日/韩) ──► NLLB 翻译模型 ──► xxx.zh.srt 中文字幕
字幕文件(srt/ass/vtt) ──────────────────────► NLLB 翻译模型 ──► xxx.zh.srt/ass/vtt
```

- **语音识别**:faster-whisper(CTranslate2)。有 NVIDIA 显卡自动用 `large-v3` + CUDA,没有则用 `small` + CPU。
- **翻译模型**(按优先级自动选择,可用 `translation_backend` 强制指定):
  1. **本机 Ollama 大模型**(检测到就自动用,如 qwen2.5:7b,动漫口语风格最佳;每次翻译完自动卸载模型释放显存);
  2. **NLLB-200-distilled-600M**(Meta 开源翻译模型,内置兜底,纯离线可用);
  3. 在 `config.json` 填任意 OpenAI 兼容接口(DeepSeek / GLM 等)则优先使用。

## 快速开始

1. **启动**:双击 `启动.bat`(首次运行自动装依赖,需等待;之后秒开),浏览器自动打开 `http://127.0.0.1:7860`
2. 上传视频或字幕文件 → 点"开始翻译" → 下载/查看中文字幕
3. **关闭**:双击 `关闭.bat`,确认显存/内存释放(脚本会打印当前显存占用)

中文字幕输出在视频同目录,命名 `视频名.zh.srt`,大多数播放器会自动加载。

## 命令行批量处理

```bat
.venv\Scripts\python.exe -X utf8 cli.py translate D:\动漫文件夹
.venv\Scripts\python.exe -X utf8 cli.py translate ep01.mkv --lang ja
.venv\Scripts\python.exe -X utf8 cli.py info
```

文件夹会递归处理所有视频/字幕;已有 `.zh` 输出的自动跳过(加 `--overwrite` 重翻)。

## 配置(config.json,首次启动自动生成)

| 配置 | 说明 |
|------|------|
| `translation_backend` | `auto` / `nllb` / `api` |
| `api.base_url/model/api_key` | OpenAI 兼容大模型接口,填了就优先用 |
| `ollama.model` | 检测到本机 Ollama 时自动使用,如 `qwen2.5:7b-instruct` |
| `asr.model_size` | `auto`/`large-v3`/`medium`/`small`,越大越准越慢 |
| `server.port` | 网页端口,默认 7860 |

## 目录结构

```
启动.bat / 关闭.bat     一键启停(关闭会释放显存内存)
cli.py                  命令行入口
subtrans/               核心代码(字幕解析、翻译后端、语音识别、网页界面)
models/                 本地模型缓存(可整个删除,下次自动重新下载)
runtime/                运行日志与 PID 文件
测试结果/                全部测试过程与报告
```

## 已知边界

- **内嵌硬字幕**(字幕烧在画面里)不识别:本工具走"语音识别"路线,适合生肉(无字幕)或外挂字幕;若视频是日语配音,对白会被完整转写翻译。
- 强 BGM 下识别率会下降(已启用 VAD 过滤,大部分动漫场景可用)。
- 测试详见 `测试结果/测试报告.md`。
