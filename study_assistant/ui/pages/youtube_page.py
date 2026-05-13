# ui/pages/youtube_page.py
"""
صفحة تلخيص YouTube — واجهة لـ YouTubeSummarizer.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from config import C

if TYPE_CHECKING:
    from main import StudyAssistant


class YouTubePage(tk.Frame):
    def __init__(self, parent: tk.Widget, app: StudyAssistant) -> None:
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self) -> None:
        tk.Label(self, text="🎬 تلخيص YouTube", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(anchor="w", padx=20, pady=16)

        input_card = tk.Frame(self, bg=C["card_bg"], padx=14, pady=12,
                              highlightbackground=C["border"], highlightthickness=1)
        input_card.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(input_card, text="رابط أو ID الفيديو:", bg=C["card_bg"],
                 fg=C["text2"], font=("Arial", 9)).pack(anchor="w")

        url_row = tk.Frame(input_card, bg=C["card_bg"])
        url_row.pack(fill="x", pady=(4, 8))
        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(url_row, textvariable=self.url_var,
                                  bg=C["surface2"], fg=C["text"], font=("Arial", 10),
                                  relief="flat", bd=6, insertbackground=C["text"])
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.bind("<Return>", lambda e: self._start_summarize())

        tk.Label(input_card, text="العنوان (اختياري):", bg=C["card_bg"],
                 fg=C["text2"], font=("Arial", 9)).pack(anchor="w")
        self.title_var = tk.StringVar()
        tk.Entry(input_card, textvariable=self.title_var,
                 bg=C["surface2"], fg=C["text"], font=("Arial", 10),
                 relief="flat", bd=6, insertbackground=C["text"]).pack(fill="x", pady=(4, 8))

        btn_row = tk.Frame(input_card, bg=C["card_bg"])
        btn_row.pack(fill="x")
        self.btn_start = tk.Button(btn_row, text="🚀 ابدأ التلخيص",
                                   command=self._start_summarize,
                                   bg=C["primary"], fg="white",
                                   font=("Arial", 11, "bold"),
                                   relief="flat", padx=18, pady=8, cursor="hand2")
        self.btn_start.pack(side="left", padx=(0, 8))
        self.status_lbl = tk.Label(btn_row, text="", bg=C["card_bg"],
                                   fg=C["text2"], font=("Arial", 9))
        self.status_lbl.pack(side="left")

        result_frame = tk.Frame(self, bg=C["bg"])
        result_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        tk.Label(result_frame, text="النتيجة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w", pady=(0, 4))

        txt_frame = tk.Frame(result_frame, bg=C["surface"],
                             highlightbackground=C["border"], highlightthickness=1)
        txt_frame.pack(fill="both", expand=True)
        self.result_txt = tk.Text(txt_frame, bg=C["surface"], fg=C["text"],
                                  font=("Consolas", 10), wrap="word",
                                  bd=0, padx=10, pady=8, state="disabled")
        vsb = ttk.Scrollbar(txt_frame, orient="vertical", command=self.result_txt.yview)
        self.result_txt.configure(yscrollcommand=vsb.set)
        self.result_txt.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        actions = tk.Frame(self, bg=C["bg"])
        actions.pack(fill="x", padx=20, pady=(0, 10))
        tk.Button(actions, text="📋 نسخ النتيجة", command=self._copy_result,
                  bg=C["surface2"], fg=C["text"], font=("Arial", 9),
                  relief="flat", padx=12, pady=5).pack(side="left", padx=(0, 6))
        tk.Button(actions, text="💾 حفظ في PDF", command=self._save_pdf,
                  bg=C["surface2"], fg=C["text"], font=("Arial", 9),
                  relief="flat", padx=12, pady=5).pack(side="left", padx=(0, 6))
        self._last_data: dict = {}
        self._last_url: str = ""
        self._last_transcript_len: int = 0

    def _set_status(self, msg: str, color: str = "") -> None:
        self.status_lbl.config(text=msg, fg=color or C["text2"])

    def _set_result(self, text: str) -> None:
        self.result_txt.config(state="normal")
        self.result_txt.delete("1.0", "end")
        self.result_txt.insert("1.0", text)
        self.result_txt.config(state="disabled")

    def _start_summarize(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("تنبيه", "أدخل رابط الفيديو")
            return

        from services.youtube import HAS_YT
        if not HAS_YT:
            messagebox.showerror("خطأ", "مكتبة youtube-transcript-api غير متوفرة")
            return

        if not self.app.groq.is_ready:
            messagebox.showwarning("تنبيه", "يرجى إعداد Groq API Key في الإعدادات أولاً")
            return

        self.btn_start.config(state="disabled")
        self._set_status("⏳ جاري جلب النص...", C["warning"])
        self._set_result("")
        threading.Thread(target=self._worker, args=(url,), daemon=True).start()

    def _worker(self, url: str) -> None:
        yt = self.app.youtube
        video_id = yt.extract_video_id(url)
        if not video_id:
            self.after(0, lambda: self._done("❌ رابط غير صحيح", "", error=True))
            return

        transcript, err = yt.fetch_transcript(video_id)
        if err:
            self.after(0, lambda: self._done(f"❌ {err}", "", error=True))
            return

        self.after(0, lambda: self._set_status("⏳ جاري التلخيص بـ AI...", C["warning"]))
        title = self.title_var.get().strip()
        data = yt.summarize(transcript, title)
        self._last_data = data
        self._last_url = url
        self._last_transcript_len = len(transcript)

        pdf_text = yt.build_pdf_text(url, title, data, len(transcript))
        self.after(0, lambda: self._done("✅ تم التلخيص!", pdf_text, error=False))

        if data.get("hard_words"):
            subject = self.app.session.subject or ""
            saved = yt.save_hard_words(data["hard_words"], subject)
            self.after(0, lambda: self._set_status(
                f"✅ تم التلخيص! — حُفظت {saved} كلمة جديدة", C["green"]))

    def _done(self, status: str, text: str, error: bool = False) -> None:
        self._set_status(status, C["danger"] if error else C["green"])
        if text:
            self._set_result(text)
        self.btn_start.config(state="normal")

    def _copy_result(self) -> None:
        text = self.result_txt.get("1.0", "end").strip()
        if not text:
            return
        try:
            import pyperclip
            pyperclip.copy(text)
            self._set_status("📋 تم النسخ!", C["green"])
        except Exception:
            pass

    def _save_pdf(self) -> None:
        text = self.result_txt.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("تنبيه", "لا توجد نتيجة لحفظها")
            return
        try:
            self.app.pdf.save_clipboard()
            self._set_status("💾 تم الحفظ في PDF!", C["green"])
        except Exception as e:
            messagebox.showerror("خطأ", str(e))
