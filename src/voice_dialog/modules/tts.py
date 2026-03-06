"""
全双工语音对话系统 v3.0 - TTS模块

支持：
- Edge TTS（默认）
- Qwen TTS
- 流式TTS播放
"""
import asyncio
import io
import re
from typing import Optional
from ..core.logger import logger

from ..core.types import TTSResult
from ..core.config import get_config


def clean_text_for_tts(text: str) -> str:
    """
    清理文本中的Markdown格式符号和表情符号，使其适合TTS播报

    处理内容：
    - Markdown格式符号（粗体、斜体、删除线、链接等）
    - 表情符号
    - 多余的空白字符
    """
    if not text:
        return text

    original_text = text

    # 1. 处理代码块（先处理多行的）
    text = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('```', '').strip(), text)
    text = re.sub(r'`([^`]+?)`', r'\1', text)  # 行内代码

    # 2. 处理链接 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # 3. 处理图片 ![alt](url) -> alt
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)

    # 4. 处理Markdown格式符号
    # 粗体 **text** 和 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)

    # 斜体 *text* 和 _text_（注意避免匹配下划线变量名）
    text = re.sub(r'(?<![a-zA-Z0-9])\*([^*]+?)\*(?![*])', r'\1', text)
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+?)_(?![a-zA-Z0-9_])', r'\1', text)

    # 删除线 ~~text~~ 和 --text--
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    text = re.sub(r'--(.+?)--', r'\1', text)

    # 5. 处理标题 # ## ### 等
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

    # 6. 处理引用 > text
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # 7. 处理列表符号
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)  # 无序列表
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)  # 有序列表

    # 8. 处理分隔线 *** --- ___
    text = re.sub(r'^(\*{3,}|-{3,}|_{3,})\s*$', '', text, flags=re.MULTILINE)

    # 9. 处理HTML标签
    text = re.sub(r'<[^>]+>', '', text)

    # 10. 移除表情符号（使用Unicode范围）
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # 表情符号
        "\U0001F300-\U0001F5FF"  # 符号和象形文字
        "\U0001F680-\U0001F6FF"  # 交通和地图符号
        "\U0001F700-\U0001F77F"  # 炼金术符号
        "\U0001F780-\U0001F7FF"  # 几何图形扩展
        "\U0001F800-\U0001F8FF"  # 补充箭头-C
        "\U0001F900-\U0001F9FF"  # 补充符号和象形文字
        "\U0001FA00-\U0001FA6F"  # 国际象棋符号
        "\U0001FA70-\U0001FAFF"  # 符号和象形文字扩展-A
        "\U00002702-\U000027B0"  # 装饰符号
        "\U000024C2-\U0001F251"
        "\U0001F004"             # 麻将牌
        "\U0001F0CF"             # 扑克牌
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)

    # 11. 清理多余的空白字符
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)
    text = text.strip()

    # 如果清理后为空，返回原文（防止过度清理）
    if not text and original_text:
        return original_text

    return text


class TTSEngine:
    """
    TTS引擎
    支持多种TTS后端: Edge TTS / Qwen TTS
    """

    def __init__(self):
        self.config = get_config().tts
        self.provider = self.config.get("provider", "edge")
        self._edge_tts = None

    async def synthesize(self, text: str) -> TTSResult:
        """
        文本转语音
        """
        # 清理文本中的格式符号和表情
        cleaned_text = clean_text_for_tts(text)

        if not cleaned_text.strip():
            return TTSResult(audio_data=b"", duration_ms=0)

        try:
            if self.provider == "edge":
                return await self._synthesize_edge(cleaned_text)
            elif self.provider == "qwen":
                return await self._synthesize_qwen(cleaned_text)
            else:
                return await self._synthesize_edge(cleaned_text)

        except Exception as e:
            logger.error(f"TTS合成失败: {e}")
            return TTSResult(audio_data=b"", duration_ms=0)

    async def _synthesize_edge(self, text: str) -> TTSResult:
        """使用Edge TTS"""
        try:
            import edge_tts

            voice = self.config.get("voice", "zh-CN-XiaoxiaoNeural")
            rate = self.config.get("rate", "+0%")
            pitch = self.config.get("pitch", "+0Hz")

            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                pitch=pitch
            )

            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            # 估算时长 (MP3约128kbps)
            duration_ms = len(audio_data) / 128 * 8

            return TTSResult(
                audio_data=audio_data,
                format="mp3",
                sample_rate=24000,
                duration_ms=duration_ms
            )

        except ImportError:
            logger.error("edge-tts未安装")
            return await self._mock_synthesize(text)

    async def _synthesize_qwen(self, text: str) -> TTSResult:
        """使用Qwen TTS"""
        # Qwen TTS API实现
        # 这里使用模拟数据
        return await self._mock_synthesize(text)

    async def _mock_synthesize(self, text: str) -> TTSResult:
        """模拟TTS（用于测试）"""
        await asyncio.sleep(0.1)

        # 生成静音音频作为占位
        # 实际使用时会被真实TTS替代
        duration_ms = len(text) * 150  # 估算时长

        return TTSResult(
            audio_data=b"\x00" * 1000,  # 模拟音频数据
            format="mp3",
            sample_rate=24000,
            duration_ms=duration_ms
        )


class StreamingTTS:
    """
    流式TTS
    支持边合成边播放
    """

    def __init__(self):
        self.engine = TTSEngine()
        self._is_playing = False
        self._should_stop = False

    async def stream_synthesize(self, text: str):
        """
        流式合成并返回音频块
        """
        # 清理文本中的格式符号和表情
        cleaned_text = clean_text_for_tts(text)

        if not cleaned_text.strip():
            return

        try:
            import edge_tts

            config = get_config().tts
            voice = config.get("voice", "zh-CN-XiaoxiaoNeural")

            communicate = edge_tts.Communicate(text=cleaned_text, voice=voice)

            self._is_playing = True
            self._should_stop = False

            async for chunk in communicate.stream():
                if self._should_stop:
                    break

                if chunk["type"] == "audio":
                    yield chunk["data"]

            self._is_playing = False

        except Exception as e:
            logger.error(f"流式TTS失败: {e}")
            self._is_playing = False

    def stop(self):
        """停止播放"""
        self._should_stop = True

    @property
    def is_playing(self) -> bool:
        return self._is_playing
