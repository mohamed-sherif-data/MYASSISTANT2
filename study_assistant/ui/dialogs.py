# ui/dialogs.py
"""
نوافذ صغيرة: بدء جلسة، إعدادات البومودورو، إضافة كلمة يدوياً،
استخراج كلمات صعبة من فقرة.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from config import C, DEFAULT_SUBJECTS

if TYPE_CHECKING:
    from main import StudyAssistant


# ══════════════════════════════════════════════════════════════════════════════
class SessionStartDialog:
    """نافذة بدء جلسة دراسة."""

    def __init__(self, app: StudyAssistant) -> None:
        self.app = app

    def show(self) -> None:
        win = tk.Toplevel(self.app.root)
        win.title("بدء جلسة")
        win.configure(bg=C["bg"])
        win.attributes("-topmost", True)
        win.resizable(False, False)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"380x390+{(sw-380)//2}+{(sh-390)//2}")

        f = tk.Frame(win, bg=C["bg"], padx=20, pady=16)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="🎓 جلسة دراسة جديدة", bg=C["bg"], fg=C["text"],
                 font=("Arial", 13, "bold")).pack(pady=(0, 14))

        tk.Label(f, text="المادة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w")
        subjects = json.loads(self.app.db.get_setting("subjects",
                               json.dumps(DEFAULT_SUBJECTS, ensure_ascii=False)))
        subj_var = tk.StringVar(value=subjects[0])
        ttk.Combobox(f, textvariable=subj_var, values=subjects,
                     state="readonly", font=("Arial", 10)).pack(fill="x", pady=(4, 10))

        tk.Label(f, text="رقم المحاضرة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w")
        lec_var = tk.IntVar(value=1)
        ttk.Spinbox(f, from_=1, to=50, textvariable=lec_var,
                    font=("Arial", 10), width=8).pack(anchor="w", pady=(4, 10))

        tk.Label(f, text="المدة (ساعات):", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w")
        dur_var = tk.DoubleVar(value=3.0)
        ttk.Spinbox(f, from_=0.5, to=12, increment=0.5, textvariable=dur_var,
                    font=("Arial", 10), width=6).pack(anchor="w", pady=(4, 10))

        pomo_var = tk.BooleanVar(value=True)
        tk.Checkbutton(f, text="🍅 بدء البومودورو تلقائياً", variable=pomo_var,
                       bg=C["bg"], fg=C["text"], selectcolor=C["surface2"],
                       font=("Arial", 9)).pack(anchor="w", pady=4)

        def _go():
            self.app.session.start(subj_var.get(), lec_var.get(), dur_var.get())
            self.app.pdf.set_lecture(subj_var.get(), lec_var.get())
            if pomo_var.get() and not self.app.pomodoro.running:
                self.app.pomodoro.start()
            win.destroy()

        tk.Button(f, text="🚀 بدء الجلسة", command=_go,
                  bg=C["primary"], fg="white",
                  font=("Arial", 11, "bold"), relief="flat",
                  padx=20, pady=8).pack(pady=10)


# ══════════════════════════════════════════════════════════════════════════════
class PomodoroSettingsDialog:
    """نافذة إعدادات البومودورو."""

    def __init__(self, app: StudyAssistant) -> None:
        self.app = app

    def show(self) -> None:
        win = tk.Toplevel(self.app.root)
        win.title("إعدادات البومودورو")
        win.configure(bg=C["bg"])
        win.attributes("-topmost", True)
        win.resizable(False, False)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"360x390+{(sw-360)//2}+{(sh-390)//2}")

        f = tk.Frame(win, bg=C["bg"], padx=20, pady=16)
        f.pack(fill="both", expand=True)
        tk.Label(f, text="⚙ إعدادات البومودورو", bg=C["bg"], fg=C["text"],
                 font=("Arial", 13, "bold")).pack(pady=(0, 14))

        cfg = self.app.pomodoro.cfg
        int_vars = {}
        for label, key, mn, mx in [
            ("مدة العمل (دقيقة)",     "work_duration",      1, 90),
            ("استراحة قصيرة",         "short_break",        1, 30),
            ("استراحة طويلة",         "long_break",         5, 60),
            ("دورات قبل الطويلة",     "cycles_before_long", 2, 8),
        ]:
            row = tk.Frame(f, bg=C["bg"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=C["bg"], fg=C["text2"],
                     font=("Arial", 9), width=26, anchor="w").pack(side="left")
            var = tk.IntVar(value=cfg.get(key, 25))
            int_vars[key] = var
            ttk.Spinbox(row, from_=mn, to=mx, textvariable=var,
                        width=6, font=("Arial", 10)).pack(side="right")

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=10)

        bool_vars: dict[str, tk.BooleanVar] = {}
        sound_var = tk.BooleanVar(value=cfg.get("sound_enabled", True))
        bool_vars["sound_enabled"] = sound_var
        tk.Checkbutton(f, text="🔔 صوت عند تغيير المرحلة", variable=sound_var,
                       bg=C["bg"], fg=C["text"], selectcolor=C["surface2"],
                       font=("Arial", 9)).pack(anchor="w", pady=2)

        summary_var = tk.BooleanVar(value=cfg.get("add_summary", True))
        bool_vars["add_summary"] = summary_var
        tk.Checkbutton(f, text="📄 إضافة ملخص PDF تلقائياً", variable=summary_var,
                       bg=C["bg"], fg=C["text"], selectcolor=C["surface2"],
                       font=("Arial", 9)).pack(anchor="w", pady=2)

        def _save():
            for k, v in int_vars.items():
                self.app.pomodoro.cfg[k] = v.get()
            for k, v in bool_vars.items():
                self.app.pomodoro.cfg[k] = v.get()
            self.app.pomodoro.save_config()
            win.destroy()

        tk.Button(f, text="💾 حفظ", command=_save,
                  bg=C["accent"], fg="white",
                  font=("Arial", 11, "bold"), relief="flat",
                  padx=20, pady=8).pack(pady=14)


# ══════════════════════════════════════════════════════════════════════════════
class AddWordDialog:
    """نافذة إضافة كلمة يدوياً مع إثراء AI اختياري."""

    def __init__(self, app: StudyAssistant, on_saved=None) -> None:
        self.app = app
        self.on_saved = on_saved

    def show(self) -> None:
        win = tk.Toplevel(self.app.root)
        win.title("➕ إضافة كلمة")
        win.configure(bg=C["bg"])
        win.attributes("-topmost", True)
        win.resizable(False, False)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"400x520+{(sw-400)//2}+{(sh-520)//2}")

        f = tk.Frame(win, bg=C["bg"], padx=20, pady=16)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="➕ إضافة كلمة جديدة", bg=C["bg"], fg=C["text"],
                 font=("Arial", 13, "bold")).pack(pady=(0, 14))

        fields = {}
        for label, key, hint in [
            ("الكلمة (إنجليزي):", "word",        "e.g. resilience"),
            ("الترجمة (عربي):",   "translation", "مرونة"),
            ("مثال إنجليزي:",     "example",     "She showed great resilience."),
            ("IPA (اختياري):",    "ipa",         "/rɪˈzɪliəns/"),
        ]:
            tk.Label(f, text=label, bg=C["bg"], fg=C["text2"],
                     font=("Arial", 9)).pack(anchor="w")
            var = tk.StringVar()
            fields[key] = var
            e = tk.Entry(f, textvariable=var, bg=C["surface2"], fg=C["text"],
                         font=("Arial", 10), relief="flat", bd=6,
                         insertbackground=C["text"])
            e.pack(fill="x", pady=(2, 8))

        row2 = tk.Frame(f, bg=C["bg"])
        row2.pack(fill="x", pady=(0, 8))
        tk.Label(row2, text="المستوى:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9), width=12, anchor="w").pack(side="left")
        lvl_var = tk.StringVar(value="B1")
        ttk.Combobox(row2, textvariable=lvl_var,
                     values=["A1", "A2", "B1", "B2", "C1", "C2"],
                     state="readonly", width=8, font=("Arial", 10)).pack(side="left")

        row3 = tk.Frame(f, bg=C["bg"])
        row3.pack(fill="x", pady=(0, 8))
        tk.Label(row3, text="المادة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9), width=12, anchor="w").pack(side="left")
        subjects = json.loads(self.app.db.get_setting("subjects",
                               json.dumps(DEFAULT_SUBJECTS, ensure_ascii=False)))
        subj_var = tk.StringVar(value=self.app.session.subject or subjects[0])
        ttk.Combobox(row3, textvariable=subj_var, values=subjects,
                     state="readonly", font=("Arial", 10)).pack(side="left", fill="x", expand=True)

        status = tk.Label(f, text="", bg=C["bg"], fg=C["text2"], font=("Arial", 9))
        status.pack()

        ai_var = tk.BooleanVar(value=self.app.groq.is_ready)
        tk.Checkbutton(f, text="✨ إثراء تلقائي بـ AI (Groq)", variable=ai_var,
                       bg=C["bg"], fg=C["green"], selectcolor=C["surface2"],
                       font=("Arial", 9)).pack(anchor="w", pady=(2, 8))

        def _save():
            word = fields["word"].get().strip()
            translation = fields["translation"].get().strip()
            if not word or not translation:
                status.config(text="⚠ الكلمة والترجمة مطلوبتان", fg=C["danger"])
                return
            if self.app.db.word_exists(word):
                status.config(text="⚠ الكلمة موجودة مسبقاً", fg=C["warning"])
                return

            status.config(text="⏳ جاري الحفظ...", fg=C["warning"])
            win.update_idletasks()

            def _worker():
                from datetime import date
                enriched = {}
                if ai_var.get() and self.app.groq.is_ready:
                    enriched = self.app.groq.enrich_word(word, translation)

                entry = {
                    "Word": word,
                    "Translation": translation,
                    "Alt_Translations": json.dumps(
                        enriched.get("alt_translations", []), ensure_ascii=False),
                    "IPA": fields["ipa"].get().strip() or enriched.get("ipa", ""),
                    "Type": enriched.get("type", "Word"),
                    "Level": lvl_var.get(),
                    "Example": fields["example"].get().strip() or enriched.get("example", ""),
                    "Example_Translation": enriched.get("example_translation", ""),
                    "Related_Words": json.dumps(
                        enriched.get("related", []), ensure_ascii=False),
                    "Synonyms": json.dumps(
                        enriched.get("synonyms", []), ensure_ascii=False),
                    "Antonyms": json.dumps(
                        enriched.get("antonyms", []), ensure_ascii=False),
                    "Sound_Alikes": json.dumps(
                        enriched.get("sound_alikes", []), ensure_ascii=False),
                    "SRS_Level": 0,
                    "Next_Review": date.today().isoformat(),
                    "Total_Reviews": 0,
                    "Correct_Reviews": 0,
                    "Subject": subj_var.get(),
                    "Added_Date": date.today().isoformat(),
                }
                ok = self.app.db.add_word(entry)
                if ok:
                    self.app.db.log_word_added()
                    self.app.sound.beep("save")

                def _done():
                    if ok:
                        status.config(text=f"✅ تم حفظ '{word}'", fg=C["green"])
                        if self.on_saved:
                            self.on_saved()
                        win.after(1200, win.destroy)
                    else:
                        status.config(text="❌ فشل الحفظ", fg=C["danger"])

                win.after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        tk.Button(f, text="💾 حفظ الكلمة", command=_save,
                  bg=C["primary"], fg="white",
                  font=("Arial", 11, "bold"), relief="flat",
                  padx=20, pady=8).pack(pady=4)


# ══════════════════════════════════════════════════════════════════════════════
class ParagraphExtractDialog:
    """استخراج الكلمات الصعبة من فقرة وحفظها."""

    def __init__(self, app: StudyAssistant, on_saved=None) -> None:
        self.app = app
        self.on_saved = on_saved

    def show(self) -> None:
        win = tk.Toplevel(self.app.root)
        win.title("📄 استخراج كلمات من فقرة")
        win.configure(bg=C["bg"])
        win.resizable(True, True)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"560x620+{(sw-560)//2}+{(sh-620)//2}")
        win.minsize(480, 500)

        f = tk.Frame(win, bg=C["bg"], padx=20, pady=14)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="📄 استخراج كلمات صعبة من فقرة", bg=C["bg"], fg=C["text"],
                 font=("Arial", 13, "bold")).pack(pady=(0, 10))
        tk.Label(f, text="الصق النص الإنجليزي هنا:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w")

        txt_frame = tk.Frame(f, bg=C["border"], padx=1, pady=1)
        txt_frame.pack(fill="both", expand=True, pady=(4, 8))
        self._text_widget = tk.Text(txt_frame, bg=C["surface2"], fg=C["text"],
                                    font=("Consolas", 10), wrap="word",
                                    insertbackground=C["text"], bd=0,
                                    height=8, padx=8, pady=8)
        vsb_t = ttk.Scrollbar(txt_frame, command=self._text_widget.yview)
        self._text_widget.configure(yscrollcommand=vsb_t.set)
        self._text_widget.pack(side="left", fill="both", expand=True)
        vsb_t.pack(side="right", fill="y")

        # خيارات
        opts = tk.Frame(f, bg=C["bg"])
        opts.pack(fill="x", pady=(0, 8))
        tk.Label(opts, text="المادة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(side="left")
        subjects = json.loads(self.app.db.get_setting("subjects",
                               json.dumps(DEFAULT_SUBJECTS, ensure_ascii=False)))
        subj_var = tk.StringVar(value=self.app.session.subject or subjects[0])
        ttk.Combobox(opts, textvariable=subj_var, values=subjects,
                     state="readonly", font=("Arial", 10),
                     width=18).pack(side="left", padx=8)

        status = tk.Label(f, text="", bg=C["bg"], fg=C["text2"], font=("Arial", 9))
        status.pack()

        btn_row = tk.Frame(f, bg=C["bg"])
        btn_row.pack(fill="x", pady=(4, 8))

        self._extract_btn = tk.Button(btn_row, text="🔍 استخراج الكلمات الصعبة",
                                      command=lambda: self._extract(win, subj_var.get(), status),
                                      bg=C["accent"], fg="white",
                                      font=("Arial", 11, "bold"), relief="flat",
                                      padx=16, pady=8, cursor="hand2")
        self._extract_btn.pack(side="left")

        # منطقة النتائج
        tk.Label(f, text="الكلمات المقترحة (اختر ما تريد حفظه):",
                 bg=C["bg"], fg=C["text2"], font=("Arial", 9)).pack(anchor="w", pady=(6, 2))
        self._result_frame = tk.Frame(f, bg=C["surface"],
                                      highlightbackground=C["border"], highlightthickness=1)
        self._result_frame.pack(fill="both", expand=True)
        self._result_lbl = tk.Label(self._result_frame, text="سيظهر هنا الاقتراح...",
                                    bg=C["surface"], fg=C["text3"],
                                    font=("Arial", 9), pady=20)
        self._result_lbl.pack()
        self._checkboxes: list[tuple[str, tk.BooleanVar]] = []
        self._save_btn = None
        self._win = win
        self._subj_var = subj_var

    def _extract(self, win, subject: str, status: tk.Label) -> None:
        text = self._text_widget.get("1.0", "end").strip()
        if not text:
            status.config(text="⚠ الصق نصاً أولاً", fg=C["warning"])
            return

        self._extract_btn.config(state="disabled")
        status.config(text="⏳ جاري الاستخراج...", fg=C["warning"])

        def _worker():
            words = self._do_extract(text)
            win.after(0, lambda: self._show_results(words, subject, status))

        threading.Thread(target=_worker, daemon=True).start()

    def _do_extract(self, text: str) -> list[str]:
        """استخراج الكلمات الصعبة: AI أو قاموس بسيط."""
        if self.app.groq.is_ready:
            prompt = (
                f"Extract 8-12 advanced/difficult English vocabulary words from this text "
                f"that an Arabic student would benefit from learning. "
                f"Return ONLY a JSON array of strings, no explanations:\n\n{text[:3000]}"
            )
            try:
                import re, json
                raw = self.app.groq._call(prompt, timeout=20)
                raw = re.sub(r"```(?:json)?", "", raw).strip("`").strip()
                match = re.search(r"\[.*\]", raw, re.DOTALL)
                if match:
                    words = json.loads(match.group())
                    return [w.strip() for w in words if isinstance(w, str) and len(w) > 3]
            except Exception:
                pass

        # Fallback: كلمات طويلة غير موجودة في القاموس الأساسي
        import re
        COMMON = {"the", "be", "to", "of", "and", "a", "in", "that", "have", "it",
                  "for", "not", "on", "with", "he", "you", "do", "at", "this", "but",
                  "they", "we", "say", "her", "she", "or", "an", "will", "my", "one",
                  "all", "would", "there", "their", "what", "so", "up", "out", "if",
                  "about", "who", "get", "which", "go", "me", "when", "make", "can",
                  "like", "time", "no", "just", "him", "know", "take", "people", "into",
                  "year", "your", "good", "some", "could", "them", "see", "other", "than",
                  "then", "now", "look", "only", "come", "its", "over", "think", "also"}
        words = re.findall(r"\b[a-zA-Z]{6,}\b", text)
        seen, result = set(), []
        for w in words:
            wl = w.lower()
            if wl not in COMMON and wl not in seen and not self.app.db.word_exists(w):
                seen.add(wl)
                result.append(w)
        return result[:12]

    def _show_results(self, words: list[str], subject: str, status: tk.Label) -> None:
        self._extract_btn.config(state="normal")
        for widget in self._result_frame.winfo_children():
            widget.destroy()
        self._checkboxes.clear()

        if not words:
            status.config(text="لم يتم العثور على كلمات جديدة", fg=C["text2"])
            tk.Label(self._result_frame, text="لا توجد كلمات جديدة للاقتراح",
                     bg=C["surface"], fg=C["text3"],
                     font=("Arial", 9), pady=10).pack()
            return

        status.config(text=f"✅ تم استخراج {len(words)} كلمة", fg=C["green"])

        scroll_c = tk.Canvas(self._result_frame, bg=C["surface"],
                             highlightthickness=0, height=150)
        vsb = ttk.Scrollbar(self._result_frame, orient="vertical",
                             command=scroll_c.yview)
        inner = tk.Frame(scroll_c, bg=C["surface"])
        inner.bind("<Configure>",
                   lambda e: scroll_c.configure(scrollregion=scroll_c.bbox("all")))
        scroll_c.create_window((0, 0), window=inner, anchor="nw")
        scroll_c.configure(yscrollcommand=vsb.set)
        scroll_c.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for word in words:
            var = tk.BooleanVar(value=True)
            self._checkboxes.append((word, var))
            tk.Checkbutton(inner, text=word, variable=var,
                           bg=C["surface"], fg=C["text"],
                           font=("Consolas", 10), selectcolor=C["surface2"],
                           activebackground=C["surface"]).pack(anchor="w", padx=8, pady=1)

        if self._save_btn:
            self._save_btn.destroy()
        self._save_btn = tk.Button(
            self._win, text="💾 حفظ المختارة",
            command=lambda: self._save_selected(subject, status),
            bg=C["primary"], fg="white",
            font=("Arial", 11, "bold"), relief="flat",
            padx=16, pady=8, cursor="hand2")
        self._save_btn.pack(pady=8)

    def _save_selected(self, subject: str, status: tk.Label) -> None:
        selected = [w for w, var in self._checkboxes if var.get()]
        if not selected:
            status.config(text="⚠ لم تختر أي كلمة", fg=C["warning"])
            return

        status.config(text="⏳ جاري الحفظ...", fg=C["warning"])
        if self._save_btn:
            self._save_btn.config(state="disabled")

        def _worker():
            saved = self.app.youtube.save_hard_words(selected, subject)
            self._win.after(0, lambda: [
                status.config(text=f"✅ تم حفظ {saved} كلمة جديدة", fg=C["green"]),
                self.app.sound.beep("save"),
                (self.on_saved() if self.on_saved else None),
            ])

        threading.Thread(target=_worker, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
class HotkeySettingsDialog:
    """نافذة تخصيص اختصارات لوحة المفاتيح."""

    def __init__(self, app: StudyAssistant) -> None:
        self.app = app

    def show(self) -> None:
        win = tk.Toplevel(self.app.root)
        win.title("⌨ اختصارات لوحة المفاتيح")
        win.configure(bg=C["bg"])
        win.attributes("-topmost", True)
        win.resizable(False, False)
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"400x340+{(sw-400)//2}+{(sh-340)//2}")

        f = tk.Frame(win, bg=C["bg"], padx=20, pady=16)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="⌨ تخصيص الاختصارات", bg=C["bg"], fg=C["text"],
                 font=("Arial", 13, "bold")).pack(pady=(0, 14))

        fields: dict[str, tk.StringVar] = {}
        descriptions = [
            ("hotkey_save",            "ctrl+x",  "اختصار حفظ PDF (Ctrl+X افتراضياً):"),
            ("hotkey_translate_key",   "c",       "مفتاح الترجمة السريعة (C افتراضياً):"),
        ]

        for key, default, label in descriptions:
            tk.Label(f, text=label, bg=C["bg"], fg=C["text2"],
                     font=("Arial", 9)).pack(anchor="w", pady=(6, 2))
            var = tk.StringVar(value=self.app.db.get_setting(key, default))
            fields[key] = var
            tk.Entry(f, textvariable=var, bg=C["surface2"], fg=C["text"],
                     font=("Consolas", 11), relief="flat", bd=6,
                     insertbackground=C["text"]).pack(fill="x")

        tk.Label(f, text="⚠ يتطلب إعادة تشغيل التطبيق لتطبيق التغييرات",
                 bg=C["bg"], fg=C["warning"], font=("Arial", 8)).pack(pady=8)

        def _save():
            for key, var in fields.items():
                val = var.get().strip()
                if val:
                    self.app.db.set_setting(key, val)
            messagebox.showinfo("تم", "تم حفظ الاختصارات.\nأعد تشغيل التطبيق للتطبيق.")
            win.destroy()

        tk.Button(f, text="💾 حفظ", command=_save,
                  bg=C["accent"], fg="white",
                  font=("Arial", 11, "bold"), relief="flat",
                  padx=20, pady=8).pack(pady=10)
