# main.py
"""
مساعد المذاكرة v8.0 — نقطة الدخول الوحيدة.
FIX: تشغيل صوت عند تغيير مراحل البومودورو.
"""

import logging
import threading
import tkinter as tk
from pathlib import Path

from core.database import Database
from core.session import SessionManager
from core.pomodoro import PomodoroTimer
from core.gamification import XPManager, DailyChallengeManager

from services.sound import SoundManager
from services.tts import TTSManager, HAS_TTS
from services.groq_client import GroqClient, GROQ_MODELS
from services.translator import TranslationManager
from services.pdf_manager import PDFManager
from services.youtube import YouTubeSummarizer, HAS_YT
from services.sentence_builder import SentenceBuilder

from ui.dashboard import Dashboard
from ui.floating_timer import FloatingTimer

logging.basicConfig(
    filename="study_assistant.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

NOTES_DIR = Path(__file__).parent / "StudyNotes"
NOTES_DIR.mkdir(exist_ok=True)


class StudyAssistant:
    """ينشئ كل المكونات ويربطها ويشغل التطبيق."""

    def __init__(self) -> None:
        logger.info("Study Assistant v8.0 starting...")

        self.db = Database()
        self.sound = SoundManager()
        self.session = SessionManager(self.db)
        self.pomodoro = PomodoroTimer(
            self.db,
            on_tick=self._on_pomo_tick,
            on_phase=self._on_pomo_phase,
        )
        self.xp = XPManager(self.db)
        self.challenge = DailyChallengeManager(self.db, self.xp)
        self.groq = GroqClient(self.db)
        self.tts = TTSManager()
        self.translator = TranslationManager(
            self.db, self.groq, self.tts, self.sound,
            get_subject=lambda: self.session.subject or "",
        )
        self.pdf = PDFManager(NOTES_DIR, sound=self.sound)
        self.youtube = YouTubeSummarizer(self.db, self.groq, self.pdf)
        self.sentences = SentenceBuilder(self.groq)

        # observer: عند حفظ كلمة جديدة
        self.db.on_word_saved(lambda total: [
            self.xp.on_word_saved(total),
            self.challenge.update("save"),
        ])

        self.root = tk.Tk()
        self.root.withdraw()

        self.translator.set_toast_callback(self._show_toast)

        # المؤقت العائم (PiP)
        self.floating_timer = FloatingTimer(self.pomodoro)

        self.dashboard = Dashboard(self)
        self._setup_hotkeys()

        if self.session.active:
            self.pdf.set_lecture(self.session.subject, self.session.lecture)

        self._setup_tray()
        logger.info("Ready ✅")

    # ── Pomodoro callbacks ─────────────────────────────────────────────────
    def _on_pomo_tick(self, remaining: int, phase: str) -> None:
        self._update_tray(remaining, phase)

    def _on_pomo_phase(self, phase: str, cycles: int) -> None:
        # FIX: تشغيل صوت عند تغيير المرحلة
        if phase == "work":
            self.sound.beep("work")
        elif phase in ("short_break", "long_break"):
            self.sound.beep("break")

        if phase in ("short_break", "long_break"):
            self.challenge.update("pomodoro")
            if self.session.active:
                self.pdf.add_summary(
                    self.session.subject or "عام",
                    self.session.lecture,
                    cycles,
                    self.pomodoro.work_minutes,
                )

    # ── Hotkeys ────────────────────────────────────────────────────────────
    def _setup_hotkeys(self) -> None:
        try:
            import keyboard
            # تحميل الاختصارات من قاعدة البيانات (قابلة للتخصيص)
            save_hotkey = self.db.get_setting("hotkey_save", "ctrl+x")
            translate_hotkey = self.db.get_setting("hotkey_translate_key", "c")
            keyboard.add_hotkey(
                save_hotkey,
                lambda: threading.Timer(0.1, self.pdf.save_clipboard).start(),
                suppress=False,
            )
            self._last_c = 0.0
            self._translate_key = translate_hotkey.lower()
            keyboard.on_press_key(translate_hotkey, self._on_c_press)
        except Exception as e:
            logger.error(f"Hotkeys setup: {e}")

    def _on_c_press(self, event) -> None:
        try:
            import keyboard
            import time
            if keyboard.is_pressed("ctrl"):
                now = time.time()
                if now - self._last_c < 0.4:
                    threading.Timer(0.15, self.translator.process_word).start()
                    self._last_c = 0.0
                else:
                    self._last_c = now
        except Exception as e:
            logger.error(f"_on_c_press: {e}")

    # ── Toast ──────────────────────────────────────────────────────────────
    def _show_toast(self, word: str, data: dict) -> None:
        def _build():
            from config import C
            t = tk.Toplevel(self.root)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            t.configure(bg=C["surface"])
            frm = tk.Frame(t, bg=C["surface"], padx=15, pady=12,
                           highlightbackground=C["border"], highlightthickness=1)
            frm.pack()
            tk.Label(frm, text=f"✅  {word}", bg=C["surface"],
                     fg=C["green"], font=("Consolas", 11, "bold")).pack()
            tk.Label(frm, text=f"→  {data.get('translation', '')}", bg=C["surface"],
                     fg=C["text"], font=("Arial", 11, "bold")).pack()
            if ex := data.get("example", ""):
                tk.Label(frm, text=f'"{ex}"', bg=C["surface"],
                         fg=C["text2"], font=("Arial", 9, "italic"),
                         wraplength=360).pack(anchor="w", pady=(3, 0))
            t.update_idletasks()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w2, h2 = t.winfo_reqwidth(), t.winfo_reqheight()
            t.geometry(f"+{sw - w2 - 20}+{sh - h2 - 60}")
            t.after(5000, t.destroy)
        self.root.after(0, _build)

    # ── Tray ───────────────────────────────────────────────────────────────
    def _setup_tray(self) -> None:
        try:
            import pystray
            from PIL import Image, ImageDraw

            def _make_icon(color=(74, 144, 217, 255)):
                img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)
                d.ellipse([2, 2, 62, 62], fill=color)
                return img

            self._tray_icon_img = _make_icon()

            def _show_app(icon, item):
                self.root.after(0, self.dashboard.show)

            def _quit_app(icon, item):
                icon.stop()
                self.root.after(0, self.root.quit)

            self.tray = pystray.Icon(
                "SA80",
                self._tray_icon_img,
                "مساعد المذاكرة v8.0",
                menu=pystray.Menu(
                    pystray.MenuItem("فتح التطبيق", _show_app, default=True),
                    pystray.MenuItem("إنهاء", _quit_app),
                )
            )
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception as e:
            logger.error(f"Tray setup: {e}")

    def _update_tray(self, remaining: int = 0, phase: str = "") -> None:
        try:
            if hasattr(self, "tray"):
                label = {
                    "work":        "🍅 عمل",
                    "short_break": "☕ استراحة",
                    "long_break":  "🛋 راحة",
                }.get(phase, "")
                m, s = remaining // 60, remaining % 60
                self.tray.title = (f"مساعد المذاكرة — {label} {m:02d}:{s:02d}"
                                   if label else "مساعد المذاكرة v8.0")
        except Exception:
            pass

    def run(self) -> None:
        self.dashboard.show()
        self.root.mainloop()


if __name__ == "__main__":
    app = StudyAssistant()
    app.run()
