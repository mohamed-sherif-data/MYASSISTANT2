# core/gamification.py
"""
نظام نقاط الخبرة والمستويات والشارات + التحدي اليومي.
يعتمد على Database لحفظ البيانات.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class XPManager:
    """نقاط الخبرة، المستوى، الشارات، وتتبع الأيام المتواصلة."""

    LEVELS = [
        (0,    "مبتدئ",  "🌱"),
        (100,  "متعلم",  "📖"),
        (300,  "متقدم",  "⭐"),
        (600,  "محترف",  "🔥"),
        (1000, "خبير",   "💎"),
        (1500, "أسطورة", "👑"),
        (2500, "عبقري",  "🧠"),
    ]

    BADGES = {
        "first_word":   ("🎯", "أول كلمة"),
        "ten_words":    ("📚", "عشرة كلمات"),
        "fifty_words":  ("🌟", "خمسون كلمة"),
        "streak_3":     ("🔥", "3 أيام متواصلة"),
        "streak_7":     ("⚡", "أسبوع كامل"),
        "perfect_quiz": ("🏆", "اختبار مثالي"),
    }

    def __init__(self, db) -> None:
        self.db = db
        self._data = self._load()

    def _load(self) -> dict:
        data = self.db.get_json_setting("xp_data") or {}
        return {
            "xp": data.get("xp", 0),
            "badges": data.get("badges", []),
            "streak": data.get("streak", 0),
            "last_streak_day": data.get("last_streak_day", ""),
        }

    def _save(self) -> None:
        self.db.set_json_setting("xp_data", self._data)

    # ── XP ────────────────────────────────────────────────────────────────
    def add_xp(self, amount: int, reason: str = "") -> None:
        self._data["xp"] += amount
        logger.info(f"XP +{amount} ({reason}) → {self._data['xp']}")
        self._save()

    def get_xp(self) -> int:
        return self._data["xp"]

    def get_level(self) -> tuple[int, str, str]:
        xp = self.get_xp()
        current = self.LEVELS[0]
        for lvl in self.LEVELS:
            if xp >= lvl[0]:
                current = lvl
        return current

    def get_level_progress(self) -> float:
        xp = self.get_xp()
        cur_idx = 0
        for i, (threshold, _, _) in enumerate(self.LEVELS):
            if xp >= threshold:
                cur_idx = i
        if cur_idx + 1 >= len(self.LEVELS):
            return 1.0
        cur_min = self.LEVELS[cur_idx][0]
        nxt_min = self.LEVELS[cur_idx + 1][0]
        return (xp - cur_min) / (nxt_min - cur_min)

    # ── Streak ────────────────────────────────────────────────────────────
    def update_streak(self) -> None:
        today = date.today().isoformat()
        last = self._data.get("last_streak_day", "")
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        if last == today:
            return
        if last == yesterday:
            self._data["streak"] += 1
        else:
            self._data["streak"] = 1
        self._data["last_streak_day"] = today
        self._save()

    def get_streak(self) -> int:
        return self._data.get("streak", 0)

    # ── Badges ────────────────────────────────────────────────────────────
    def award_badge(self, badge_id: str) -> bool:
        if badge_id not in self._data["badges"]:
            self._data["badges"].append(badge_id)
            self._save()
            logger.info(f"Badge awarded: {badge_id}")
            return True
        return False

    def get_badges(self) -> list[str]:
        return self._data.get("badges", [])

    # ── Event callbacks ────────────────────────────────────────────────────
    def on_word_saved(self, total_words: int) -> None:
        self.add_xp(10, "حفظ كلمة")
        self.update_streak()
        if total_words == 1:  self.award_badge("first_word")
        if total_words >= 10: self.award_badge("ten_words")
        if total_words >= 50: self.award_badge("fifty_words")
        streak = self.get_streak()
        if streak >= 3: self.award_badge("streak_3")
        if streak >= 7: self.award_badge("streak_7")

    def on_quiz_complete(self, pct: int, count: int) -> None:
        earned = int(count * (pct / 100) * 5)
        self.add_xp(earned, f"اختبار {pct}%")
        if pct == 100 and count >= 5:
            self.award_badge("perfect_quiz")


class DailyChallengeManager:
    """تحدي يومي يتجدد تلقائياً."""

    TYPES = {
        "review":   "راجع {n} كلمات مستحقة اليوم",
        "save":     "احفظ {n} كلمات جديدة اليوم",
        "quiz":     "حل اختباراً بدقة {n}% أو أكثر",
        "pomodoro": "أكمل {n} دورة بومودورو اليوم",
    }

    def __init__(self, db, xp_manager: XPManager) -> None:
        self.db = db
        self.xp = xp_manager
        self._data = self._load()
        self._ensure_today()

    def _load(self) -> dict:
        return self.db.get_json_setting("daily_challenge") or {}

    def _save(self) -> None:
        self.db.set_json_setting("daily_challenge", self._data)

    def _ensure_today(self) -> None:
        today = date.today().isoformat()
        if self._data.get("date") == today:
            return

        ctype, template = random.choice(list(self.TYPES.items()))
        n = {
            "quiz":     random.choice([70, 80, 90, 100]),
            "pomodoro": random.choice([2, 3, 4]),
        }.get(ctype, random.choice([3, 5, 7, 10]))

        self._data = {
            "date": today, "type": ctype, "n": n,
            "text": template.format(n=n),
            "completed": False, "progress": 0,
        }
        self._save()

    def get(self) -> dict:
        return dict(self._data)

    def update(self, event_type: str, amount: int = 1) -> None:
        if self._data.get("completed"):
            return
        if self._data.get("type") != event_type:
            return

        self._data["progress"] = min(
            self._data.get("progress", 0) + amount,
            self._data.get("n", 1),
        )
        if self._data["progress"] >= self._data["n"]:
            self._data["completed"] = True
            self.xp.add_xp(50, "تحدي يومي")
            logger.info("Daily challenge completed! +50 XP")
        self._save()

    def is_done(self) -> bool:
        return self._data.get("completed", False)