# ui/pages/chatbot.py
"""
صفحة Chatbot — محادثة ذكية بالكلمات المحفوظة.
تستخدم Groq وتُدرج كلمات الطالب في الإجابات.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from config import C

if TYPE_CHECKING:
    from main import StudyAssistant

_SYSTEM_PROMPT = """You are an intelligent English tutor for Arabic-speaking students.
Rules:
1. Answer in simple English. Add Arabic translation for new vocabulary in (parentheses).
2. When you use one of the student's saved words, put it in *asterisks*.
3. If the student writes in Arabic, respond in Arabic then repeat key English words.
4. Focus on vocabulary building, grammar tips, and encouraging practice.
5. Keep responses concise (3-5 sentences max unless the student asks for more).
6. Use the student's saved words naturally in your sentences whenever possible.
"""


class ChatbotPage(tk.Frame):
    def __init__(self, parent: tk.Widget, app: StudyAssistant) -> None:
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._history: list[dict] = []
        self._saved_words: list[str] = []
        self._build()

    def _build(self) -> None:
        hdr = tk.Frame(self, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=12)
        tk.Label(hdr, text="💬 Chatbot المساعد التعليمي", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(side="left")
        self._status_lbl = tk.Label(hdr, text="", bg=C["bg"], fg=C["text3"],
                                    font=("Arial", 8))
        self._status_lbl.pack(side="left", padx=12)
        tk.Button(hdr, text="🗑 مسح المحادثة", command=self._clear,
                  bg=C["surface2"], fg=C["text2"], font=("Arial", 9),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="right")

        if not self.app.groq.is_ready:
            tk.Label(self, text="⚠ الـ Chatbot يحتاج مفتاح Groq API.\nأضفه من صفحة الإعدادات.",
                     bg=C["bg"], fg=C["warning"],
                     font=("Arial", 11)).pack(expand=True)
            return

        # منطقة المحادثة
        chat_outer = tk.Frame(self, bg=C["surface"],
                              highlightbackground=C["border"], highlightthickness=1)
        chat_outer.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        self._chat_canvas = tk.Canvas(chat_outer, bg=C["surface"],
                                      highlightthickness=0)
        vsb = ttk.Scrollbar(chat_outer, orient="vertical",
                             command=self._chat_canvas.yview)
        self._messages_frame = tk.Frame(self._chat_canvas, bg=C["surface"])
        self._messages_frame.bind(
            "<Configure>",
            lambda e: self._chat_canvas.configure(
                scrollregion=self._chat_canvas.bbox("all")))
        self._chat_canvas.create_window((0, 0), window=self._messages_frame, anchor="nw")
        self._chat_canvas.configure(yscrollcommand=vsb.set)
        self._chat_canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Suggestions (أسئلة سريعة)
        sug_frame = tk.Frame(self, bg=C["bg"])
        sug_frame.pack(fill="x", padx=20, pady=(0, 6))
        suggestions = [
            "Use my saved words in a story",
            "What's the difference between similar words?",
            "Quiz me on my weakest words",
            "Correct my English grammar",
        ]
        for sug in suggestions:
            tk.Button(sug_frame, text=sug,
                      command=lambda s=sug: self._send_msg(s),
                      bg=C["surface2"], fg=C["text2"], font=("Arial", 8),
                      relief="flat", padx=8, pady=3, cursor="hand2").pack(
                          side="left", padx=2)

        # شريط الإدخال
        inp = tk.Frame(self, bg=C["surface"],
                       highlightbackground=C["border"], highlightthickness=1)
        inp.pack(fill="x", padx=20, pady=(0, 14))

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(inp, textvariable=self._input_var,
                                     bg=C["surface"], fg=C["text"],
                                     font=("Arial", 11), relief="flat",
                                     insertbackground=C["text"], bd=8)
        self._input_entry.pack(side="left", fill="both", expand=True)
        self._input_entry.bind("<Return>", lambda e: self._send())
        self._input_entry.bind("<Shift-Return>", lambda e: None)

        self._send_btn = tk.Button(inp, text="إرسال ⟶",
                                   command=self._send,
                                   bg=C["accent"], fg="white",
                                   font=("Arial", 10, "bold"),
                                   relief="flat", padx=16, pady=8, cursor="hand2")
        self._send_btn.pack(side="right")

        # تحميل الكلمات + رسالة ترحيب
        self._load_words()
        self._add_bot_message(
            "مرحباً! 👋 أنا مساعدك التعليمي. لديك "
            f"{len(self._saved_words)} كلمة محفوظة."
            "\n\nيمكنني:\n• استخدام كلماتك في جمل وقصص\n"
            "• تصحيح قواعدك الإنجليزية\n"
            "• اختبارك بكلماتك الضعيفة\n"
            "• شرح الفروق بين الكلمات المتشابهة\n\n"
            "ماذا تريد أن تفعل اليوم؟"
        )

    def _load_words(self) -> None:
        try:
            words = self.app.db.load_words()
            self._saved_words = [w["word"] for w in words[:80] if w.get("word")]
        except Exception:
            self._saved_words = []

    def _build_context(self) -> str:
        if self._saved_words:
            sample = ", ".join(self._saved_words[:30])
            return f"\n\nStudent's saved words (use these naturally): {sample}"
        return ""

    def _send(self) -> None:
        msg = self._input_var.get().strip()
        if not msg:
            return
        self._input_var.set("")
        self._send_msg(msg)

    def _send_msg(self, msg: str) -> None:
        self._add_user_message(msg)
        self._input_entry.config(state="disabled")
        self._send_btn.config(state="disabled")
        self._status_lbl.config(text="⏳ يكتب...")
        self._history.append({"role": "user", "content": msg})

        def _worker():
            try:
                context = self._build_context()
                system = _SYSTEM_PROMPT + context
                # بناء prompt مع التاريخ (آخر 6 رسائل فقط)
                history_text = ""
                for turn in self._history[-6:]:
                    role = "Student" if turn["role"] == "user" else "Tutor"
                    history_text += f"{role}: {turn['content']}\n"
                prompt = f"{system}\n\nConversation:\n{history_text}Tutor:"
                reply = self.app.groq._call(prompt, timeout=25)
                reply = reply.strip()
                self._history.append({"role": "assistant", "content": reply})
            except Exception as e:
                reply = f"⚠ خطأ في الاتصال: {e}"
            self.after(0, lambda: self._on_reply(reply))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_reply(self, reply: str) -> None:
        self._add_bot_message(reply)
        self._input_entry.config(state="normal")
        self._send_btn.config(state="normal")
        self._status_lbl.config(text="")
        self._input_entry.focus_set()

    def _add_user_message(self, text: str) -> None:
        f = tk.Frame(self._messages_frame, bg=C["surface"])
        f.pack(fill="x", padx=12, pady=4)
        bubble = tk.Frame(f, bg=C["accent"], padx=12, pady=8)
        bubble.pack(side="right")
        tk.Label(bubble, text=text, bg=C["accent"], fg="white",
                 font=("Arial", 10), wraplength=420, justify="right").pack()
        tk.Label(f, text="أنت", bg=C["surface"], fg=C["text3"],
                 font=("Arial", 7)).pack(side="right", padx=4, anchor="s")
        self._scroll_bottom()

    def _add_bot_message(self, text: str) -> None:
        f = tk.Frame(self._messages_frame, bg=C["surface"])
        f.pack(fill="x", padx=12, pady=4)
        tk.Label(f, text="🤖", bg=C["surface"], fg=C["text"],
                 font=("Arial", 14)).pack(side="left", anchor="n", padx=(0, 6))
        bubble = tk.Frame(f, bg=C["card_bg"],
                          highlightbackground=C["border"], highlightthickness=1,
                          padx=12, pady=8)
        bubble.pack(side="left", fill="x", expand=True)
        tk.Label(bubble, text=text, bg=C["card_bg"], fg=C["text"],
                 font=("Arial", 10), wraplength=480, justify="left").pack(anchor="w")
        self._scroll_bottom()

    def _scroll_bottom(self) -> None:
        self.after(50, lambda: self._chat_canvas.yview_moveto(1.0))

    def _clear(self) -> None:
        self._history.clear()
        for w in self._messages_frame.winfo_children():
            w.destroy()
        self._add_bot_message("تم مسح المحادثة. كيف يمكنني مساعدتك؟ 😊")
