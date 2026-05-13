# ui/flashcards.py
"""
نافذة مراجعة البطاقات التعليمية (Flashcards) بنظام SRS.
تعرض الكلمات المستحقة مع تقييم: لم أتذكر / صعبة / تذكرت / سهلة.
"""

from __future__ import annotations

import json
import random
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from config import C, LEVEL_COLORS
from services.tts import HAS_TTS

if TYPE_CHECKING:
    from main import StudyAssistant


class FlashcardsWindow:
    """نافذة مراجعة بطاقات SRS."""

    def __init__(self, app: StudyAssistant, subject_filter: str = "الكل") -> None:
        self.app = app
        self.subject_filter = subject_filter
        self.words: list[dict] = []
        self.current_index = 0
        self.flipped = False
        self.correct_count = 0
        self.total_reviewed = 0
        self.win: tk.Toplevel | None = None

    def show(self) -> None:
        """فتح النافذة وبدء المراجعة."""
        # جلب الكلمات المستحقة مع الفلتر
        due = self.app.db.get_due_words()
        if self.subject_filter != "الكل":
            due = [w for w in due if w.get("subject", "") == self.subject_filter]

        if not due:
            from tkinter import messagebox
            messagebox.showinfo("مراجعة", "🎉 لا توجد كلمات مستحقة اليوم!")
            return

        random.shuffle(due)
        self.words = due
        self.current_index = 0
        self.correct_count = 0
        self.total_reviewed = 0
        self.flipped = False

        # إنشاء النافذة
        self.win = tk.Toplevel(self.app.root)
        title_suffix = f" [{self.subject_filter}]" if self.subject_filter != "الكل" else ""
        self.win.title(f"🃏 مراجعة — {len(due)} كلمة{title_suffix}")
        self.win.configure(bg=C["bg"])
        self.win.resizable(True, True)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = 660, 560
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.win.minsize(540, 460)
        self._build()
        self._load_card()
        self.win.bind("<space>", lambda e: self._flip())
        self.win.bind("1", lambda e: self._rate(0))
        self.win.bind("2", lambda e: self._rate(1))
        self.win.bind("3", lambda e: self._rate(2))
        self.win.bind("4", lambda e: self._rate(3))

    def _build(self) -> None:
        """بناء واجهة النافذة."""
        # شريط التقدم
        top = tk.Frame(self.win, bg=C["surface"], pady=8, padx=16)
        top.pack(fill="x")
        self.lbl_progress = tk.Label(top, text="", bg=C["surface"],
                                     fg=C["text2"], font=("Consolas", 10))
        self.lbl_progress.pack(side="left")
        self.lbl_score = tk.Label(top, text="✅ 0  ❌ 0", bg=C["surface"],
                                  fg=C["text2"], font=("Consolas", 10))
        self.lbl_score.pack(side="right")
        self.pbar_var = tk.DoubleVar()
        ttk.Progressbar(self.win, variable=self.pbar_var,
                        maximum=len(self.words)).pack(fill="x")

        # منطقة البطاقة
        card_area = tk.Frame(self.win, bg=C["bg"])
        card_area.pack(fill="both", expand=True, padx=18, pady=14)

        self.card = tk.Frame(card_area, bg=C["card_bg"],
                             highlightbackground=C["border"], highlightthickness=1)
        self.card.pack(fill="both", expand=True)
        self.card.bind("<Button-1>", lambda e: self._flip())

        # الوجه الأمامي
        self.front = tk.Frame(self.card, bg=C["card_bg"])
        self.lbl_word = tk.Label(self.front, text="", bg=C["card_bg"],
                                 fg=C["text"], font=("Georgia", 36, "bold"),
                                 wraplength=500)
        self.lbl_word.pack(pady=20)
        self.lbl_ipa = tk.Label(self.front, text="", bg=C["card_bg"],
                                fg=C["text3"], font=("Arial", 12, "italic"))
        self.lbl_ipa.pack()
        self.lbl_level = tk.Label(self.front, text="", bg=C["card_bg"],
                                  font=("Consolas", 9, "bold"))
        self.lbl_level.pack(pady=4)
        tk.Label(self.front, text="اضغط Space أو انقر للترجمة", bg=C["card_bg"],
                 fg=C["text3"], font=("Arial", 8)).pack(pady=10)

        # الوجه الخلفي
        self.back = tk.Frame(self.card, bg=C["card_bg"])
        self.lbl_word_back = tk.Label(self.back, text="", bg=C["card_bg"],
                                      fg=C["text3"], font=("Georgia", 16))
        self.lbl_word_back.pack(pady=(16, 2))
        self.lbl_translation = tk.Label(self.back, text="", bg=C["card_bg"],
                                        fg=C["green"], font=("Arial", 30, "bold"),
                                        wraplength=500)
        self.lbl_translation.pack(pady=4)
        self.lbl_example = tk.Label(self.back, text="", bg=C["card_bg"],
                                    fg=C["text2"], font=("Arial", 10, "italic"),
                                    wraplength=500)
        self.lbl_example.pack(pady=8)
        self.lbl_related = tk.Label(self.back, text="", bg=C["card_bg"],
                                    fg=C["purple"], font=("Arial", 9),
                                    wraplength=500)
        self.lbl_related.pack()

        # أزرار التحكم
        btn_frame = tk.Frame(self.win, bg=C["bg"], pady=8)
        btn_frame.pack(fill="x", padx=18)

        self.btn_flip = tk.Button(btn_frame, text="↩  اقلب البطاقة",
                                  command=self._flip, bg=C["accent"], fg="white",
                                  font=("Arial", 11, "bold"), relief="flat",
                                  padx=14, pady=9, cursor="hand2")
        self.btn_flip.pack(fill="x")

        self.rate_frame = tk.Frame(btn_frame, bg=C["bg"])
        # سنخفيها مؤقتاً
        for text, color, quality in [
            ("❌  لم أتذكر", C["danger"], 0),
            ("⚠️  صعبة",    C["warning"], 1),
            ("✅  تذكرت",   C["primary"], 2),
            ("⚡  سهلة",    C["purple"],  3),
        ]:
            tk.Button(self.rate_frame, text=text,
                      command=lambda q=quality: self._rate(q),
                      bg=color, fg="white",
                      font=("Arial", 11, "bold"), relief="flat",
                      padx=14, pady=9, cursor="hand2").pack(
                          side="left", expand=True, fill="x", padx=2)

        # عرض الوجه الأمامي بداية
        self.front.pack(fill="both", expand=True)
        self.back.pack_forget()
        self.rate_frame.pack_forget()

    def _load_card(self) -> None:
        """تحميل الكلمة الحالية."""
        if self.current_index >= len(self.words):
            self._show_summary()
            return

        w = self.words[self.current_index]
        self.flipped = False

        # الوجه الأمامي
        self.lbl_word.config(text=w.get("word", ""))
        self.lbl_ipa.config(text=w.get("ipa", ""))
        lvl = w.get("level", "")
        self.lbl_level.config(text=f"● {lvl}", fg=LEVEL_COLORS.get(lvl, C["text2"]))

        # الوجه الخلفي (يُملأ لكنه مخفي)
        self.lbl_word_back.config(text=w.get("word", ""))
        self.lbl_translation.config(text=w.get("translation", ""))
        self.lbl_example.config(text=w.get("example", ""))
        # الكلمات المترابطة
        related_raw = w.get("related_words", "[]")
        related_parts = []
        try:
            related = json.loads(related_raw)
            related_parts = [
                f"{r.get('word','')} ({r.get('translation','')})"
                for r in related[:3]
                if isinstance(r, dict) and r.get("word")
            ]
        except:
            pass
        self.lbl_related.config(text="🔗 " + "  •  ".join(related_parts) if related_parts else "")

        # إعادة تعيين الواجهة
        self.front.pack(fill="both", expand=True)
        self.back.pack_forget()
        self.btn_flip.pack(fill="x")
        self.rate_frame.pack_forget()

        # تحديث شريط التقدم
        self.lbl_progress.config(text=f"{self.current_index + 1} / {len(self.words)}")
        self.pbar_var.set(self.current_index)
        self.lbl_score.config(text=f"✅ {self.correct_count}  ❌ {self.total_reviewed - self.correct_count}")

        # نطق الكلمة تلقائياً (اختياري)
        if HAS_TTS:
            self.app.tts.speak_word(w.get("word", ""))

    def _flip(self) -> None:
        """قلب البطاقة لإظهار الترجمة."""
        if self.flipped:
            return
        self.flipped = True
        self.app.sound.beep("flip")
        self.front.pack_forget()
        self.back.pack(fill="both", expand=True)
        self.btn_flip.pack_forget()
        self.rate_frame.pack(fill="x")

    def _rate(self, quality: int) -> None:
        """تقييم البطاقة وتحديث SRS."""
        w = self.words[self.current_index]
        self.total_reviewed += 1
        if quality >= 2:
            self.correct_count += 1
            self.app.sound.beep("correct")
        else:
            self.app.sound.beep("wrong")

        # تحديث SRS في قاعدة البيانات
        self.app.db.update_srs(w["word"], quality)
        
        # تسجيل للمراجعة لتتبع نقاط الضعف
        try:
            self.app.db.log_review(w["word"], quality, "flashcard", 0)
        except Exception:
            pass

        self.current_index += 1
        self._load_card()

    def _show_summary(self) -> None:
        """عرض ملخص الجلسة."""
        for widget in self.win.winfo_children():
            widget.destroy()

        accuracy = int(self.correct_count / self.total_reviewed * 100) if self.total_reviewed else 0
        f = tk.Frame(self.win, bg=C["bg"])
        f.pack(fill="both", expand=True, padx=30, pady=20)

        tk.Label(f, text="🎉", bg=C["bg"], font=("Arial", 46)).pack(pady=(16, 0))
        tk.Label(f, text="انتهت جلسة المراجعة!", bg=C["bg"], fg=C["text"],
                 font=("Arial", 17, "bold")).pack(pady=8)

        stats_card = tk.Frame(f, bg=C["surface"], padx=24, pady=16,
                              highlightbackground=C["border"], highlightthickness=1)
        stats_card.pack(fill="x", pady=16)
        for label, value, color in [
            ("مراجَعة",     str(self.total_reviewed), C["blue"]),
            ("صحيحة",       str(self.correct_count),   C["green"]),
            ("خاطئة",       str(self.total_reviewed - self.correct_count), C["danger"]),
            ("نسبة النجاح", f"{accuracy}%", C["green"] if accuracy >= 70 else C["warning"]),
        ]:
            row = tk.Frame(stats_card, bg=C["surface"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=C["surface"], fg=C["text2"],
                     font=("Arial", 10), width=14, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=C["surface"], fg=color,
                     font=("Consolas", 13, "bold")).pack(side="right")

        # تحديث XP والتحدي
        if self.total_reviewed > 0:
            self.app.xp.on_quiz_complete(accuracy, self.total_reviewed)
            self.app.challenge.update("quiz", self.correct_count)

        tk.Button(f, text="✖  إغلاق", command=self.win.destroy,
                  bg=C["surface2"], fg=C["text"], font=("Arial", 11),
                  relief="flat", padx=20, pady=8).pack(pady=16)