# ui/pages/settings.py
"""
صفحة الإعدادات — Groq API، البومودورو، المواد، تخصيص الاختصارات.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from config import C, DEFAULT_SUBJECTS
from services.groq_client import GROQ_MODELS

if TYPE_CHECKING:
    from main import StudyAssistant


class SettingsPage(tk.Frame):
    def __init__(self, parent: tk.Widget, app: StudyAssistant) -> None:
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self) -> None:
        canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=C["bg"])
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 * int(e.delta / 120), "units"))

        f = scroll_frame
        tk.Label(f, text="⚙️ الإعدادات", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(anchor="w", padx=20, pady=16)

        # ── Groq API ───────────────────────────────────────────────────────
        gc = self._card(f, "⚡ Groq API")
        gc.pack(fill="x", padx=20, pady=(0, 10))

        status_clr = C["green"] if self.app.groq.is_ready else C["danger"]
        status_txt = "✅ متصل" if self.app.groq.is_ready else "❌ غير متصل"
        self._status_lbl = tk.Label(gc, text=status_txt, bg=C["card_bg"],
                                    fg=status_clr, font=("Arial", 10))
        self._status_lbl.pack(anchor="w")

        tk.Label(gc, text="النموذج:", bg=C["card_bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w", pady=(8, 2))
        self.model_var = tk.StringVar(value=self.app.groq.model)
        ttk.Combobox(gc, textvariable=self.model_var, values=GROQ_MODELS,
                     state="readonly", font=("Consolas", 9)).pack(fill="x", pady=(0, 6))

        tk.Label(gc, text="API Key (Primary):", bg=C["card_bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w", pady=(4, 2))
        key_row = tk.Frame(gc, bg=C["card_bg"])
        key_row.pack(fill="x")
        self.key_var = tk.StringVar(value=self.app.db.get_setting("GROQ_API_KEY", ""))
        tk.Entry(key_row, textvariable=self.key_var, bg=C["surface2"], fg=C["text"],
                 font=("Consolas", 9), relief="flat", bd=6, show="*").pack(
                     side="left", fill="x", expand=True)
        tk.Button(key_row, text="💾 حفظ واختبار",
                  command=self._save_groq,
                  bg=C["accent"], fg="white", font=("Arial", 9),
                  relief="flat", padx=10, pady=4).pack(side="left", padx=(8, 0))

        # API Key الثاني (Rotation)
        tk.Label(gc, text="API Key (Backup — للتبادل التلقائي):",
                 bg=C["card_bg"], fg=C["text2"], font=("Arial", 9)).pack(anchor="w", pady=(8, 2))
        key2_row = tk.Frame(gc, bg=C["card_bg"])
        key2_row.pack(fill="x")
        self.key2_var = tk.StringVar(value=self.app.db.get_setting("GROQ_API_KEY2", ""))
        tk.Entry(key2_row, textvariable=self.key2_var, bg=C["surface2"], fg=C["text"],
                 font=("Consolas", 9), relief="flat", bd=6, show="*").pack(
                     side="left", fill="x", expand=True)
        tk.Button(key2_row, text="💾 حفظ",
                  command=self._save_key2,
                  bg=C["surface2"], fg=C["text2"], font=("Arial", 9),
                  relief="flat", padx=10, pady=4).pack(side="left", padx=(8, 0))

        # ── المواد ─────────────────────────────────────────────────────────
        sc = self._card(f, "📚 إدارة المواد")
        sc.pack(fill="x", padx=20, pady=(0, 10))
        self.subj_frame = tk.Frame(sc, bg=C["card_bg"])
        self.subj_frame.pack(fill="x", pady=(0, 8))
        add_row = tk.Frame(sc, bg=C["card_bg"])
        add_row.pack(fill="x")
        self.new_subj_var = tk.StringVar()
        tk.Entry(add_row, textvariable=self.new_subj_var, bg=C["surface2"],
                 fg=C["text"], font=("Arial", 10), relief="flat", bd=6).pack(
                     side="left", fill="x", expand=True)
        tk.Button(add_row, text="➕ إضافة", command=self._add_subject,
                  bg=C["primary"], fg="white", font=("Arial", 9),
                  relief="flat", padx=10, pady=5).pack(side="left", padx=(6, 0))
        self._refresh_subjects()

        # ── البومودورو ─────────────────────────────────────────────────────
        bc = self._card(f, "🍅 إعدادات البومودورو")
        bc.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(bc, text="⚙ فتح إعدادات البومودورو",
                  command=self._pomo_settings,
                  bg=C["surface2"], fg=C["text2"], font=("Arial", 10),
                  relief="flat", padx=14, pady=6).pack(anchor="w")

        # ── اختصارات لوحة المفاتيح ─────────────────────────────────────────
        hc = self._card(f, "⌨ اختصارات لوحة المفاتيح")
        hc.pack(fill="x", padx=20, pady=(0, 10))

        self._hotkey_fields: dict[str, tk.StringVar] = {}
        for key, default, label in [
            ("hotkey_save",          "ctrl+x", "حفظ PDF:"),
            ("hotkey_translate_key", "c",      "مفتاح الترجمة السريعة:"),
        ]:
            row = tk.Frame(hc, bg=C["card_bg"])
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, bg=C["card_bg"], fg=C["text2"],
                     font=("Arial", 9), width=26, anchor="w").pack(side="left")
            var = tk.StringVar(value=self.app.db.get_setting(key, default))
            self._hotkey_fields[key] = var
            tk.Entry(row, textvariable=var, bg=C["surface2"], fg=C["text"],
                     font=("Consolas", 10), relief="flat", bd=4, width=16).pack(side="left")

        tk.Label(hc, text="⚠ أعد تشغيل التطبيق لتطبيق التغييرات",
                 bg=C["card_bg"], fg=C["warning"], font=("Arial", 8)).pack(anchor="w", pady=(4, 2))
        tk.Button(hc, text="💾 حفظ الاختصارات", command=self._save_hotkeys,
                  bg=C["accent"], fg="white", font=("Arial", 9),
                  relief="flat", padx=12, pady=5).pack(anchor="w", pady=(4, 0))

        # ── معلومات النظام ─────────────────────────────────────────────────
        ic = self._card(f, "ℹ معلومات النظام")
        ic.pack(fill="x", padx=20, pady=(0, 14))
        import platform, sys
        for label, value in [
            ("إصدار Python:", sys.version.split()[0]),
            ("النظام:",       platform.system()),
            ("الإصدار:",      "8.0.0"),
            ("قاعدة البيانات:", str(self.app.db.db_path)),
        ]:
            row = tk.Frame(ic, bg=C["card_bg"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=C["card_bg"], fg=C["text2"],
                     font=("Arial", 8), width=20, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=C["card_bg"], fg=C["text"],
                     font=("Consolas", 8)).pack(side="left")

    def _card(self, parent, title: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=C["card_bg"], padx=14, pady=10,
                         highlightbackground=C["border"], highlightthickness=1)
        tk.Label(frame, text=title, bg=C["card_bg"], fg=C["text2"],
                 font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 6))
        return frame

    def _save_groq(self) -> None:
        key = self.key_var.get().strip()
        model = self.model_var.get()
        if not key or len(key) < 20:
            messagebox.showwarning("تنبيه", "المفتاح قصير جداً")
            return

        def _test():
            success = self.app.groq.set_key(key, model)
            msg = "تم الاتصال بنجاح! ✅" if success else "فشل الاتصال ❌"
            color = C["green"] if success else C["danger"]
            self._status_lbl.config(
                text="✅ متصل" if success else "❌ غير متصل", fg=color)
            if success:
                messagebox.showinfo("Groq", msg)
            else:
                messagebox.showerror("Groq", msg)

        threading.Thread(target=_test, daemon=True).start()

    def _save_key2(self) -> None:
        key2 = self.key2_var.get().strip()
        if key2:
            self.app.db.set_setting("GROQ_API_KEY2", key2)
            # إعطاء الـ GroqClient القائمة الكاملة
            try:
                self.app.groq.set_backup_key(key2)
            except AttributeError:
                pass
            messagebox.showinfo("تم", "تم حفظ المفتاح الاحتياطي")

    def _save_hotkeys(self) -> None:
        for key, var in self._hotkey_fields.items():
            val = var.get().strip()
            if val:
                self.app.db.set_setting(key, val)
        messagebox.showinfo("تم", "تم حفظ الاختصارات.\nأعد التشغيل للتطبيق.")

    def _refresh_subjects(self) -> None:
        for w in self.subj_frame.winfo_children():
            w.destroy()
        subjects = json.loads(self.app.db.get_setting(
            "subjects", json.dumps(DEFAULT_SUBJECTS, ensure_ascii=False)))
        for s in subjects:
            row = tk.Frame(self.subj_frame, bg=C["card_bg"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=s, bg=C["card_bg"], fg=C["text"],
                     font=("Arial", 10)).pack(side="left", padx=4)
            if s != "بدون مادة":
                tk.Button(row, text="✕",
                          command=lambda sub=s: self._del_subject(sub),
                          bg=C["card_bg"], fg=C["danger"],
                          font=("Arial", 9), relief="flat",
                          padx=4, cursor="hand2").pack(side="right")

    def _add_subject(self) -> None:
        name = self.new_subj_var.get().strip()
        if not name:
            return
        subjects = json.loads(self.app.db.get_setting(
            "subjects", json.dumps(DEFAULT_SUBJECTS, ensure_ascii=False)))
        if name not in subjects:
            subjects.append(name)
            self.app.db.set_setting(
                "subjects", json.dumps(subjects, ensure_ascii=False))
        self.new_subj_var.set("")
        self._refresh_subjects()

    def _del_subject(self, name: str) -> None:
        subjects = json.loads(self.app.db.get_setting(
            "subjects", json.dumps(DEFAULT_SUBJECTS, ensure_ascii=False)))
        if name in subjects and name != "بدون مادة":
            subjects.remove(name)
            self.app.db.set_setting(
                "subjects", json.dumps(subjects, ensure_ascii=False))
            self._refresh_subjects()

    def _pomo_settings(self) -> None:
        from ui.dialogs import PomodoroSettingsDialog
        PomodoroSettingsDialog(self.app).show()
