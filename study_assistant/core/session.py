# core/session.py
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Optional
from .database import Database

logger = logging.getLogger(__name__)

class SessionManager:
    """يدير جلسة الدراسة الحالية (مادة، محاضرة، وقت متبقي)."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.active = False
        self.subject: Optional[str] = None
        self.lecture: int = 1
        self.start_time: Optional[datetime] = None
        self.duration_hours: float = 3.0
        self._restore()

    def _restore(self) -> None:
        """استعادة الجلسة من قاعدة البيانات إذا كانت لم تنتهِ."""
        data = self.db.get_json_setting("current_session")
        if not data:
            return
        try:
            start = datetime.fromisoformat(data["start_time"])
            duration = data.get("duration_hours", 3.0)
            elapsed = (datetime.now() - start).total_seconds() / 3600
            if elapsed < duration:
                self.active = True
                self.subject = data.get("subject")
                self.lecture = data.get("lecture_num", 1)
                self.start_time = start
                self.duration_hours = duration
        except Exception as e:
            logger.error(f"Session restore failed: {e}")

    def start(self, subject: str, lecture: int, duration_hours: float = 3.0) -> None:
        self.active = True
        self.subject = subject
        self.lecture = lecture
        self.start_time = datetime.now()
        self.duration_hours = duration_hours
        self._save()
        logger.info(f"Session started: {subject} L{lecture:02d}")

    def end(self, work_minutes: int = 0) -> None:
        if self.active and work_minutes > 0:
            self.db.log_session(work_minutes, self.subject or "")
        self.active = False
        self.subject = None
        self.start_time = None
        self.db.set_json_setting("current_session", None)
        logger.info("Session ended")

    def _save(self) -> None:
        if self.active and self.start_time:
            self.db.set_json_setting("current_session", {
                "subject": self.subject,
                "lecture_num": self.lecture,
                "start_time": self.start_time.isoformat(),
                "duration_hours": self.duration_hours,
            })

    @property
    def remaining(self) -> timedelta:
        if not self.active or not self.start_time:
            return timedelta(0)
        elapsed = datetime.now() - self.start_time
        total = timedelta(hours=self.duration_hours)
        remaining = total - elapsed
        return remaining if remaining.total_seconds() > 0 else timedelta(0)

    def remaining_str(self) -> str:
        r = self.remaining
        minutes = int(r.total_seconds() // 60)
        return f"{minutes // 60}:{minutes % 60:02d}"

    def status(self) -> str:
        if not self.active:
            return "لا توجد جلسة"
        return f"{self.subject or 'عام'} — L{self.lecture:02d}"