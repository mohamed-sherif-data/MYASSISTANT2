# services/tts.py
"""
TTSManager للنطق الصوتي (gTTS + pygame).
يعمل بخيوط منفصلة ولا يعرف شيئاً عن الـ UI.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
    import pygame
    pygame.mixer.init()
    HAS_TTS = True
except ImportError:
    HAS_TTS = False
    logger.warning("TTS not available")

CACHE_DIR = Path(__file__).parent.parent / ".tts_cache"


class TTSManager:
    """نطق النصوص الإنجليزية مع cache لتجنب إعادة التوليد."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        CACHE_DIR.mkdir(exist_ok=True)

    @staticmethod
    def _cache_path(text: str, lang: str = "en") -> Path:
        key = re.sub(r"[^\w]", "_", f"{lang}_{text[:60]}")
        return CACHE_DIR / f"{key}.mp3"

    def speak(self, text: str, lang: str = "en") -> None:
        if not HAS_TTS or not text:
            return
        threading.Thread(target=self._speak_worker, args=(text, lang), daemon=True).start()

    def _speak_worker(self, text: str, lang: str) -> None:
        try:
            cached = self._cache_path(text, lang)
            with self._lock:
                if not cached.exists():
                    buf = BytesIO()
                    gTTS(text=text, lang=lang, slow=False).write_to_fp(buf)
                    cached.write_bytes(buf.getvalue())
            pygame.mixer.music.load(str(cached))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"TTS error: {e}")

    def speak_word(self, word: str) -> None:
        self.speak(word, "en")

    def speak_example(self, example: str) -> None:
        self.speak(example, "en")

    def speak_word_then_example(self, word: str, example: str) -> None:
        def _seq():
            self._speak_worker(word, "en")
            if example:
                time.sleep(0.4)
                self._speak_worker(example, "en")
        threading.Thread(target=_seq, daemon=True).start()