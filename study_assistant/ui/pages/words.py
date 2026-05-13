# ui/pages/words.py
"""
صفحة الكلمات — إضافة يدوية، استخراج من فقرة، حذف، بحث (على cache)، AI.
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from config import C
from services.tts import HAS_TTS

if TYPE_CHECKING:
    from main import StudyAssistant


class WordsPage(tk.Frame):
    def __init__(self, parent: tk.Widget, app: StudyAssistant) -> None:
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._words_cache: list[dict] = []
        self._build()

    def _build(self) -> None:
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=14)
        tk.Label(hdr, text="📋 جميع الكلمات", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(side="left")

        # أزرار الجانب الأيمن
        for text, cmd, clr in reversed([
            ("➕ إضافة",       self._add_word,       C["primary"]),
            ("📄 استخراج",    self._extract_words,   C["accent"]),
            ("📖 قصة AI",     self._generate_story,  C["teal"]),
            ("💬 حوار AI",    self._generate_dialogue, C["purple"]),
            ("📝 تمارين AI",  self._generate_exercises, C["warning"]),
            ("🗑 حذف",        self._delete_selected, C["danger"]),
        ]):
            tk.Button(hdr, text=text, command=cmd,
                      bg=clr, fg="white", font=("Arial", 9),
                      relief="flat", padx=10, pady=4,
                      cursor="hand2").pack(side="right", padx=2)

        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(sf, text="🔍", bg=C["bg"], fg=C["text2"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *_: self._apply_filter())
        tk.Entry(sf, textvariable=self.search_var, bg=C["surface2"], fg=C["text"],
                 font=("Arial", 10), relief="flat", insertbackground=C["text"],
                 bd=6).pack(side="left", fill="x", expand=True, padx=8)

        # جدول الكلمات
        table_frame = tk.Frame(self, bg=C["bg"])
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        self.tree = ttk.Treeview(table_frame,
                                  columns=("word", "trans", "ipa", "type", "level", "srs", "added"),
                                  show="headings")
        for col, head, width in [
            ("word",  "الكلمة",   120), ("trans", "الترجمة", 150),
            ("ipa",   "IPA",      100), ("type",  "النوع",    60),
            ("level", "مستوى",    55),  ("srs",   "SRS",      40),
            ("added", "أُضيفت",   90),
        ]:
            self.tree.heading(col, text=head)
            self.tree.column(col, width=width, anchor="center")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._speak_word)
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)

        # لوحة التفاصيل
        self.detail = tk.Frame(self, bg=C["card_bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        self.detail.pack(fill="x", padx=20, pady=(0, 10))
        self._detail_hint = tk.Label(self.detail, text="اختر كلمة لعرض تفاصيلها",
                                     bg=C["card_bg"], fg=C["text3"],
                                     font=("Arial", 9), pady=6)
        self._detail_hint.pack()
        self._refresh()

    def _refresh(self) -> None:
        self._words_cache = self.app.db.load_words()
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search_var.get().lower().strip()
        for row in self.tree.get_children():
            self.tree.delete(row)
        for w in reversed(self._words_cache):
            if query and (query not in w.get("word", "").lower()
                          and query not in w.get("translation", "").lower()):
                continue
            self.tree.insert("", "end", values=(
                w.get("word", ""), w.get("translation", ""), w.get("ipa", ""),
                w.get("type", ""), w.get("level", ""),
                "★" * min(int(w.get("srs_level", 0) or 0), 6),
                w.get("added_date", ""),
            ))

    def _show_detail(self, event=None) -> None:
        for wdg in self.detail.winfo_children():
            wdg.destroy()
        sel = self.tree.selection()
        if not sel:
            tk.Label(self.detail, text="اختر كلمة لعرض تفاصيلها",
                     bg=C["card_bg"], fg=C["text3"],
                     font=("Arial", 9), pady=6).pack()
            return
        word = self.tree.item(sel[0], "values")[0]
        entry = next((w for w in self._words_cache if w["word"] == word), None)
        if not entry:
            return

        f = tk.Frame(self.detail, bg=C["card_bg"], padx=12, pady=8)
        f.pack(fill="x")
        top = tk.Frame(f, bg=C["card_bg"])
        top.pack(fill="x")
        tk.Label(top, text=entry.get("word", ""), bg=C["card_bg"], fg=C["text"],
                 font=("Georgia", 16, "bold")).pack(side="left")
        if ipa := entry.get("ipa", ""):
            tk.Label(top, text=f"  {ipa}", bg=C["card_bg"], fg=C["text3"],
                     font=("Arial", 10, "italic")).pack(side="left")
        if HAS_TTS:
            tk.Button(top, text="🔊", command=lambda: self.app.tts.speak_word(entry["word"]),
                      bg=C["card_bg"], fg=C["blue"], font=("Arial", 10),
                      relief="flat", cursor="hand2").pack(side="left", padx=4)

        trans = entry.get("translation", "")
        alts = []
        try:
            alts = json.loads(entry.get("alt_translations", "[]"))
        except Exception:
            pass
        all_trans = [t for t in [trans] + alts if t]
        tk.Label(f, text=" →  " + "  |  ".join(all_trans[:4]), bg=C["card_bg"],
                 fg=C["green"], font=("Arial", 11, "bold"),
                 wraplength=600, anchor="w").pack(anchor="w")

        if ex := entry.get("example", ""):
            tk.Label(f, text=f'"{ex}"', bg=C["card_bg"], fg=C["text2"],
                     font=("Arial", 9, "italic"), wraplength=600).pack(anchor="w", pady=(4, 0))
        if ex_ar := entry.get("example_trans", ""):
            tk.Label(f, text=f"↳ {ex_ar}", bg=C["card_bg"], fg=C["text3"],
                     font=("Arial", 8), wraplength=600).pack(anchor="w")

        syns, ants = [], []
        try:
            syns = [s["word"] for s in json.loads(entry.get("synonyms", "[]"))[:3]
                    if isinstance(s, dict) and s.get("word")]
        except Exception:
            pass
        try:
            ants = [a["word"] for a in json.loads(entry.get("antonyms", "[]"))[:2]
                    if isinstance(a, dict) and a.get("word")]
        except Exception:
            pass
        if syns:
            tk.Label(f, text="≈ " + "  •  ".join(syns), bg=C["card_bg"],
                     fg=C["green"], font=("Arial", 9)).pack(anchor="w")
        if ants:
            tk.Label(f, text="≠ " + "  •  ".join(ants), bg=C["card_bg"],
                     fg=C["danger"], font=("Arial", 9)).pack(anchor="w")

    def _speak_word(self, event=None) -> None:
        if not HAS_TTS:
            return
        sel = self.tree.selection()
        if sel:
            self.app.tts.speak_word(self.tree.item(sel[0], "values")[0])

    def _add_word(self) -> None:
        from ui.dialogs import AddWordDialog
        AddWordDialog(self.app, on_saved=self._refresh).show()

    def _extract_words(self) -> None:
        from ui.dialogs import ParagraphExtractDialog
        ParagraphExtractDialog(self.app, on_saved=self._refresh).show()

    def _delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("تنبيه", "اختر كلمة أولاً")
            return
        word = self.tree.item(sel[0], "values")[0]
        if messagebox.askyesno("حذف", f'هل تريد حذف "{word}" نهائياً؟'):
            if self.app.db.delete_word(word):
                self.app.sound.beep("normal")
                self._refresh()
                for wdg in self.detail.winfo_children():
                    wdg.destroy()
                tk.Label(self.detail, text="تم الحذف", bg=C["card_bg"],
                         fg=C["danger"], font=("Arial", 9), pady=6).pack()
            else:
                messagebox.showerror("خطأ", "لم يتم العثور على الكلمة")

    def _get_random_words(self, n: int = 6) -> list[str]:
        import random
        pool = [w["word"] for w in self._words_cache[:60] if w.get("word")]
        return random.sample(pool, min(n, len(pool))) if len(pool) >= 3 else []

    def _show_ai_result(self, title: str, content: str) -> None:
        win = tk.Toplevel(self.app.root)
        win.title(title)
        win.configure(bg=C["bg"])
        win.geometry("540x440")
        f = tk.Frame(win, bg=C["bg"], padx=20, pady=14)
        f.pack(fill="both", expand=True)
        tk.Label(f, text=title, bg=C["bg"], fg=C["text"],
                 font=("Arial", 12, "bold")).pack(pady=(0, 8))
        txt = tk.Text(f, bg=C["surface"], fg=C["text"],
                      font=("Consolas", 10), wrap="word", height=14, bd=0,
                      padx=8, pady=8)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", content)
        txt.config(state="disabled")
        tk.Button(f, text="📋 نسخ",
                  command=lambda: self.app.root.clipboard_clear() or
                  self.app.root.clipboard_append(content),
                  bg=C["surface2"], fg=C["text"],
                  font=("Arial", 10), relief="flat", padx=16, pady=6).pack(pady=8)

    def _generate_story(self) -> None:
        selected = self._get_random_words(6)
        if not selected:
            messagebox.showinfo("تنبيه", "أضف 3 كلمات على الأقل")
            return
        import threading
        def _worker():
            story = self.app.sentences.generate_story(selected)
            self.after(0, lambda: self._show_ai_result("📖 قصة من كلماتك", story))
        threading.Thread(target=_worker, daemon=True).start()

    def _generate_dialogue(self) -> None:
        selected = self._get_random_words(5)
        if not selected:
            messagebox.showinfo("تنبيه", "أضف 3 كلمات على الأقل")
            return
        import threading
        def _worker():
            dialogue = self.app.sentences.generate_dialogue(selected)
            self.after(0, lambda: self._show_ai_result("💬 حوار من كلماتك", dialogue))
        threading.Thread(target=_worker, daemon=True).start()

    def _generate_exercises(self) -> None:
        selected = self._get_random_words(8)
        if not selected:
            messagebox.showinfo("تنبيه", "أضف 3 كلمات على الأقل")
            return
        import threading
        def _worker():
            exercises = self.app.sentences.generate_exercises(selected, "fill_blank")
            self.after(0, lambda: self._show_ai_result("📝 تمارين من كلماتك", exercises))
        threading.Thread(target=_worker, daemon=True).start()
