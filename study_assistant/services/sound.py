# services/sound.py
"""
SoundManager مستقل لتشغيل نغمات النظام.
يدعم Windows (winsound) وLinux/Mac (pygame beep).
"""

from __future__ import annotations

import logging
import platform
import threading
import time

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()


class SoundManager:
    """أصوات غير متزامنة (non-blocking) متوافقة مع Windows وLinux."""

    PATTERNS = {
        "work":     [(800,150),(900,150),(1000,150),(1100,150),(1200,150)],
        "break":    [(1200,150),(1100,150),(1000,150),(900,150),(800,150)],
        "finished": [(1000,200),(0,200),(1000,200),(0,200),(1000,200),
                     (0,200),(1000,200),(0,200),(1000,200)],
        "save":     [(600,100),(800,100),(1000,100)],
        "note":     [(880,300)],
        "error":    [(300,500)],
        "flip":     [(500,80)],
        "correct":  [(800,100),(1000,150)],
        "wrong":    [(400,200)],
        "normal":   [(750,200)],
    }

    def beep(self, pattern: str = "normal") -> None:
        threading.Thread(target=self._play, args=(pattern,), daemon=True).start()

    def _play(self, pattern: str) -> None:
        steps = self.PATTERNS.get(pattern, self.PATTERNS["normal"])
        if _SYSTEM == "Windows":
            self._play_windows(steps)
        else:
            self._play_pygame(steps)

    def _play_windows(self, steps: list) -> None:
        try:
            import winsound
            for freq, dur in steps:
                if freq == 0:
                    time.sleep(dur / 1000)
                else:
                    winsound.Beep(freq, dur)
                    time.sleep(0.04)
        except Exception as e:
            logger.debug(f"Sound (windows) error: {e}")

    def _play_pygame(self, steps: list) -> None:
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            import numpy as np
            sample_rate = 44100
            for freq, dur_ms in steps:
                if freq == 0:
                    time.sleep(dur_ms / 1000)
                    continue
                dur_s = dur_ms / 1000
                t = np.linspace(0, dur_s, int(sample_rate * dur_s), endpoint=False)
                wave = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
                stereo = np.column_stack([wave, wave])
                sound = pygame.sndarray.make_sound(stereo)
                sound.play()
                time.sleep(dur_s + 0.04)
        except Exception as e:
            logger.debug(f"Sound (pygame) error: {e}")
