# core/pomodoro.py
from __future__ import annotations

import threading
import time
import logging
from typing import Callable, Optional

# FIX: حذف استيراد Database غير الضروري الذي كان يسبب مشكلة في الاستيراد النسبي
# from .database import Database

logger = logging.getLogger(__name__)

PHASE_LABELS = {
    "work":        "🍅 عمل",
    "short_break": "☕ استراحة",
    "long_break":  "🛋 راحة طويلة",
}

DEFAULT_CONFIG = {
    "work_duration":      25,
    "short_break":        5,
    "long_break":         15,
    "cycles_before_long": 4,
}


class PomodoroTimer:
    """مؤقت بومودورو مستقل. يُشغَّل في خيط، ويُخطر عبر callbacks."""

    def __init__(self, db,
                 on_tick: Optional[Callable[[int, str], None]] = None,
                 on_phase: Optional[Callable[[str, int], None]] = None) -> None:
        self.db = db
        self.on_tick = on_tick
        self.on_phase = on_phase

        self.running = False
        self.paused = False
        self.phase: str = "idle"
        self.cycles = 0
        self.work_minutes = 0
        self.remaining = 0
        self._stop_event = threading.Event()
        self._load_config()

    def _load_config(self) -> None:
        saved = self.db.get_json_setting("pomodoro_config") or {}
        self.cfg = {**DEFAULT_CONFIG, **saved}
        for k in DEFAULT_CONFIG:
            self.cfg[k] = int(self.cfg.get(k, DEFAULT_CONFIG[k]))

    def save_config(self) -> None:
        self.db.set_json_setting("pomodoro_config", self.cfg)

    @property
    def is_running(self) -> bool:
        return self.running

    def _duration(self) -> int:
        key = {
            "work":        "work_duration",
            "short_break": "short_break",
            "long_break":  "long_break",
        }.get(self.phase, "work_duration")
        return self.cfg[key] * 60

    def _advance_phase(self) -> None:
        if self.phase == "work":
            self.cycles += 1
            self.work_minutes += self.cfg["work_duration"]
            long_every = self.cfg["cycles_before_long"]
            self.phase = "long_break" if self.cycles % long_every == 0 else "short_break"
        else:
            self.phase = "work"
        self.remaining = self._duration()
        if self.on_phase:
            self.on_phase(self.phase, self.cycles)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            if self.running and not self.paused:
                if self.remaining > 0:
                    self.remaining -= 1
                    if self.on_tick:
                        self.on_tick(self.remaining, self.phase)
                else:
                    self._advance_phase()
            time.sleep(1)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.paused = False
        self.phase = "work"
        self.remaining = self._duration()
        self._stop_event.clear()
        threading.Thread(target=self._loop, daemon=True).start()
        logger.info("Pomodoro started")

    def pause(self) -> None:
        self.paused = not self.paused

    def skip(self) -> None:
        self._advance_phase()

    def stop(self) -> None:
        self.running = False
        self.paused = False
        self.phase = "idle"
        self.remaining = 0
        self._stop_event.set()
        logger.info("Pomodoro stopped")

    def time_str(self) -> str:
        if not self.running:
            # FIX: عرض المدة الافتراضية عند التوقف بدلاً من 00:00
            m = self.cfg.get("work_duration", 25)
            return f"{m:02d}:00"
        m, s = self.remaining // 60, self.remaining % 60
        return f"{m:02d}:{s:02d}"

    def status_label(self) -> str:
        if not self.running:
            return "⏹ متوقف"
        if self.paused:
            return "⏸ مؤقت"
        return PHASE_LABELS.get(self.phase, "")
