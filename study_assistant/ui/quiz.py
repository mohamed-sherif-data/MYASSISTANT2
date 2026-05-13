# ui/quiz.py
"""
نافذة الاختبار (7 أنماط): اختيار، عكسي، كتابة، استماع، إملاء، ترتيب، ملء فراغات.
FIX: cache all_words مرة واحدة عند بدء الاختبار بدلاً من load من DB مع كل سؤال.
FIX: lbl_prog يُحدَّث في _load_question.
"""

from __future__ import annotations

import json
import random
import re
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING

from config import C, LEVEL_COLORS
from services.tts import HAS_TTS

if TYPE_CHECKING:
    from main import StudyAssistant

QUIZ_MODES = [
    ("🔤  اختيار من متعدد",        "mc_en_ar"),
    ("🔄  عكسي (عربي→إنجليزي)",   "mc_ar_en"),
    ("✍   اكتب الإجابة",           "write"),
    ("👂  استماع (كلمات متشابهة)", "listen"),
    ("🎙  إملاء صوتي",             "dictation"),
    ("🔀  رتّب الجملة",            "word_order"),
    ("📝  ملء الفراغات",           "fill_blank"),
]


class QuizWindow:
    """نافذة اختبار الكلمات التفاعلي."""

    def __init__(self, app: StudyAssistant, default_subject: str = "الكل") -> None:
        self.app = app
        self.default_subject = default_subject
        self.words: list[dict] = []
        self._all_words: list[dict] = []  # cache — يُملأ مرة واحدة عند البدء
        self.mode = "mc_en_ar"
        self.current_index = 0
        self.correct_count = 0
        self.total_answered = 0
        self.answered = False
        self.win: tk.Toplevel | None = None

    # ── إعداد ─────────────────────────────────────────────────────────────
    def show(self) -> None:
        setup = tk.Toplevel(self.app.root)
        setup.title("🎯 إعداد الاختبار")
        setup.configure(bg=C["bg"])
        setup.resizable(True, True)
        sw, sh = setup.winfo_screenwidth(), setup.winfo_screenheight()
        setup.geometry(f"420x490+{(sw-420)//2}+{(sh-490)//2}")
        setup.minsize(380, 420)
        setup.attributes("-topmost", True)

        f = tk.Frame(setup, bg=C["bg"], padx=24, pady=20)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="🎯 اختبار الكلمات", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(pady=(0, 12))

        tk.Label(f, text="نوع الاختبار:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9)).pack(anchor="w")
        mode_var = tk.StringVar(value="mc_en_ar")
        for label, value in QUIZ_MODES:
            tk.Radiobutton(f, text=label, variable=mode_var, value=value,
                           bg=C["bg"], fg=C["text"], selectcolor=C["surface2"],
                           activebackground=C["bg"], font=("Arial", 10)).pack(anchor="w", pady=1)

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=8)

        row1 = tk.Frame(f, bg=C["bg"]); row1.pack(fill="x", pady=2)
        tk.Label(row1, text="المادة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9), width=14, anchor="w").pack(side="left")
        # load once for setup dialog only
        all_w = self.app.db.load_words()
        subjects = ["الكل"] + sorted({w.get("subject", "") for w in all_w if w.get("subject")})
        subj_var = tk.StringVar(value=self.default_subject if self.default_subject in subjects else "الكل")
        ttk.Combobox(row1, textvariable=subj_var, values=subjects,
                     state="readonly", font=("Arial", 10)).pack(side="left", fill="x", expand=True)

        row2 = tk.Frame(f, bg=C["bg"]); row2.pack(fill="x", pady=2)
        tk.Label(row2, text="عدد الأسئلة:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9), width=14, anchor="w").pack(side="left")
        count_var = tk.IntVar(value=10)
        ttk.Spinbox(row2, from_=5, to=50, textvariable=count_var,
                    font=("Arial", 10), width=8).pack(side="left")

        row3 = tk.Frame(f, bg=C["bg"]); row3.pack(fill="x", pady=2)
        tk.Label(row3, text="مستوى الكلمات:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 9), width=14, anchor="w").pack(side="left")
        lvl_var = tk.StringVar(value="الكل")
        ttk.Combobox(row3, textvariable=lvl_var,
                     values=["الكل", "A1", "A2", "B1", "B2", "C1", "C2"],
                     state="readonly", font=("Arial", 10), width=8).pack(side="left")

        status_lbl = tk.Label(f, text="", bg=C["bg"], fg=C["danger"], font=("Arial", 9))
        status_lbl.pack(pady=4)

        def _start():
            pool = [w for w in all_w
                    if (subj_var.get() == "الكل" or w.get("subject", "") == subj_var.get())
                    and (lvl_var.get() == "الكل" or w.get("level", "") == lvl_var.get())]
            if len(pool) < 4:
                status_lbl.config(text=f"⚠ تحتاج 4 كلمات على الأقل! (لديك {len(pool)})")
                return
            random.shuffle(pool)
            n = min(count_var.get(), len(pool))
            self.words = pool[:n]
            self._all_words = all_w  # cache كامل القائمة مرة واحدة
            self.mode = mode_var.get()
            self.current_index = 0
            self.correct_count = 0
            self.total_answered = 0
            self.answered = False
            setup.destroy()
            self._open_quiz()

        tk.Button(f, text="🚀 بدء الاختبار", command=_start,
                  bg=C["primary"], fg="white", font=("Arial", 12, "bold"),
                  relief="flat", padx=24, pady=10, cursor="hand2").pack(pady=(6, 0))

    # ── نافذة الاختبار ─────────────────────────────────────────────────────
    def _open_quiz(self) -> None:
        title = dict(QUIZ_MODES).get(self.mode, "اختبار")
        self.win = tk.Toplevel(self.app.root)
        self.win.title(f"{title} — {len(self.words)} سؤال")
        self.win.configure(bg=C["bg"])
        self.win.resizable(True, True)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = 680, 600
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.win.minsize(560, 480)
        self.win.bind("<Return>", lambda e: self._on_enter())
        self._build_ui()
        self._load_question()

    def _build_ui(self) -> None:
        top = tk.Frame(self.win, bg=C["surface"], pady=8, padx=16)
        top.pack(fill="x")
        self.lbl_prog = tk.Label(top, text="", bg=C["surface"], fg=C["text2"],
                                 font=("Consolas", 10))
        self.lbl_prog.pack(side="left")
        self.lbl_score = tk.Label(top, text="✅ 0  ❌ 0", bg=C["surface"],
                                  fg=C["text2"], font=("Consolas", 10))
        self.lbl_score.pack(side="right")
        self.pbar_var = tk.DoubleVar()
        ttk.Progressbar(self.win, variable=self.pbar_var,
                        maximum=len(self.words)).pack(fill="x")

        q_area = tk.Frame(self.win, bg=C["bg"])
        q_area.pack(fill="both", expand=True, padx=20, pady=14)

        self.q_card = tk.Frame(q_area, bg=C["card_bg"],
                               highlightbackground=C["border"], highlightthickness=1)
        self.q_card.pack(fill="x", pady=(0, 12))
        self.q_inner = tk.Frame(self.q_card, bg=C["card_bg"], padx=20, pady=16)
        self.q_inner.pack(fill="x")

        self.lbl_question = tk.Label(self.q_inner, text="", bg=C["card_bg"],
                                     fg=C["text"], font=("Georgia", 30, "bold"),
                                     wraplength=560, justify="center")
        self.lbl_question.pack(pady=(4, 4))
        self.lbl_ipa = tk.Label(self.q_inner, text="", bg=C["card_bg"],
                                fg=C["text3"], font=("Arial", 11, "italic"))
        self.lbl_ipa.pack()
        self.btn_speak = tk.Button(self.q_inner, text="🔊 نطق",
                                   command=self._speak_current,
                                   bg=C["surface2"], fg=C["blue"],
                                   font=("Arial", 9), relief="flat",
                                   padx=10, pady=3, cursor="hand2")
        self.btn_speak.pack(pady=(4, 0))

        self.ans_frame = tk.Frame(q_area, bg=C["bg"])
        self.ans_frame.pack(fill="both", expand=True)

    # ── تحميل السؤال ─────────────────────────────────────────────────────
    def _load_question(self) -> None:
        if self.current_index >= len(self.words):
            self._show_summary()
            return
        self.answered = False
        w = self.words[self.current_index]
        self._start_time = time.time()

        # FIX: تحديث شريط التقدم النصي (كان يُترك فارغاً)
        self.lbl_prog.config(text=f"السؤال {self.current_index + 1} / {len(self.words)}")
        self.pbar_var.set(self.current_index)
        self.lbl_score.config(
            text=f"✅ {self.correct_count}  ❌ {self.total_answered - self.correct_count}")

        if self.mode == "listen":
            self.lbl_question.config(text="🔊  ?", fg=C["text2"],
                                     font=("Georgia", 30, "bold"))
            self.lbl_ipa.config(text="استمع ثم اختر الكلمة الصحيحة")
            self.btn_speak.config(state="normal")
            if HAS_TTS:
                threading.Timer(0.5, lambda: self.app.tts.speak_word(
                    w.get("word", ""))).start()
        elif self.mode == "dictation":
            self.lbl_question.config(text="🎙  ?", fg=C["text2"],
                                     font=("Georgia", 30, "bold"))
            self.lbl_ipa.config(text="استمع واكتب الكلمة بالإنجليزي")
            self.btn_speak.config(state="normal")
            if HAS_TTS:
                threading.Timer(0.5, lambda: self.app.tts.speak_word(
                    w.get("word", ""))).start()
        elif self.mode == "word_order":
            self.lbl_question.config(
                text=f"رتّب الجملة:\n{w.get('translation', '')}",
                fg=C["text"], font=("Arial", 14, "bold"))
            self.lbl_ipa.config(text="اضغط الكلمات بالترتيب الصحيح")
            self.btn_speak.config(state="disabled")
        elif self.mode == "fill_blank":
            self.lbl_question.config(text="أكمل الجملة بالكلمة المناسبة",
                                     fg=C["text2"], font=("Arial", 13))
            self.lbl_ipa.config(text="")
            self.btn_speak.config(state="disabled")
        elif self.mode in ("mc_en_ar", "write"):
            self.lbl_question.config(text=w.get("word", ""), fg=C["text"],
                                     font=("Georgia", 30, "bold"))
            self.lbl_ipa.config(text=w.get("ipa", ""))
            self.btn_speak.config(state="normal")
        else:  # mc_ar_en
            self.lbl_question.config(text=w.get("translation", ""),
                                     fg=C["text"], font=("Georgia", 28, "bold"))
            self.lbl_ipa.config(text="")
            self.btn_speak.config(state="disabled")

        for child in self.ans_frame.winfo_children():
            child.destroy()

        builders = {
            "write":      self._build_write,
            "dictation":  self._build_dictation,
            "word_order": self._build_word_order,
            "fill_blank": self._build_fill_blank,
            "listen":     self._build_listen,
        }
        if self.mode in builders:
            builders[self.mode](w)
        else:
            self._build_mc(w)

    # ── MC / Listen ────────────────────────────────────────────────────────
    def _build_mc(self, correct: dict) -> None:
        # FIX: يستخدم self._all_words (cached) بدلاً من load_words() من DB
        distractors = [w for w in self._all_words if w.get("word", "") != correct.get("word", "")]
        random.shuffle(distractors)

        if self.mode == "mc_en_ar":
            correct_ans = correct.get("translation", "")
            options = [(w.get("translation", ""), False) for w in distractors[:3]]
        elif self.mode == "mc_ar_en":
            correct_ans = correct.get("word", "")
            options = [(w.get("word", ""), False) for w in distractors[:3]]
        elif self.mode == "listen":
            correct_ans = correct.get("word", "")
            sound_alikes = self._get_sound_alikes(correct)
            options = [(w, False) for w in sound_alikes if w != correct_ans][:3]
        else:
            correct_ans = correct.get("word", "")
            options = [(w.get("word", ""), False) for w in distractors[:3]]

        options.append((correct_ans, True))
        random.shuffle(options)

        self._mc_buttons = []
        for text, is_correct in options:
            btn = tk.Button(self.ans_frame, text=f"  {text}",
                            bg=C["surface"], fg=C["text"], font=("Arial", 12),
                            relief="flat", anchor="w", padx=20, pady=12,
                            cursor="hand2", wraplength=500,
                            highlightbackground=C["border"], highlightthickness=1,
                            command=lambda c=is_correct: self._mc_answer(c))
            btn.pack(fill="x", pady=4)
            self._mc_buttons.append((btn, is_correct))

    def _mc_answer(self, is_correct: bool) -> None:
        if self.answered:
            return
        self.answered = True
        self.total_answered += 1
        for btn, correct in self._mc_buttons:
            btn.config(state="disabled", cursor="arrow")
            if correct:
                btn.config(bg=C["primary"], fg="white")
            else:
                btn.config(bg=C["surface2"], fg=C["text3"])
        self._evaluate(is_correct)

    def _get_sound_alikes(self, correct: dict) -> list[str]:
        word = correct.get("word", "")
        raw = correct.get("sound_alikes", "[]")
        try:
            alikes = json.loads(raw)
            if isinstance(alikes, list) and len(alikes) >= 3:
                return alikes
        except Exception:
            pass
        # FIX: يستخدم self._all_words (cached)
        others = [w.get("word", "") for w in self._all_words if w.get("word", "") != word]
        random.shuffle(others)
        return others[:4]

    # ── كتابة ──────────────────────────────────────────────────────────────
    def _build_write(self, word: dict) -> None:
        f = tk.Frame(self.ans_frame, bg=C["bg"])
        f.pack(fill="x", pady=10)
        tk.Label(f, text="اكتب الترجمة بالعربي:", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 10)).pack(anchor="w")
        self.write_var = tk.StringVar()
        self.write_entry = tk.Entry(f, textvariable=self.write_var, bg=C["surface2"],
                                    fg=C["text"], font=("Arial", 16),
                                    relief="flat", bd=10, justify="right")
        self.write_entry.pack(fill="x", pady=6)
        self.write_entry.focus_set()
        self.write_result = tk.Label(f, text="", bg=C["bg"], font=("Arial", 12))
        self.write_result.pack()
        tk.Button(f, text="✓ تحقق", command=self._check_write,
                  bg=C["accent"], fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=16, pady=9, cursor="hand2").pack(pady=8)

    def _check_write(self) -> None:
        if self.answered:
            return
        self.answered = True
        self.total_answered += 1
        correct_tr = self.words[self.current_index].get("translation", "").strip()
        user_ans = self.write_var.get().strip()
        is_correct = self._normalize(user_ans) == self._normalize(correct_tr)
        self.write_entry.config(state="disabled")
        if is_correct:
            self.write_result.config(text=f"✅ صح! الإجابة: {correct_tr}", fg=C["green"])
        else:
            self.write_result.config(text=f"❌ خطأ — الصواب: {correct_tr}", fg=C["danger"])
        self._evaluate(is_correct)

    # ── إملاء ──────────────────────────────────────────────────────────────
    def _build_dictation(self, word: dict) -> None:
        f = tk.Frame(self.ans_frame, bg=C["bg"])
        f.pack(fill="x", pady=10)
        tk.Label(f, text="اكتب الكلمة التي سمعتها:", bg=C["bg"],
                 fg=C["text2"], font=("Arial", 10)).pack()
        self.dict_var = tk.StringVar()
        self.dict_entry = tk.Entry(f, textvariable=self.dict_var, bg=C["surface2"],
                                   fg=C["text"], font=("Consolas", 18),
                                   relief="flat", bd=10, justify="center")
        self.dict_entry.pack(fill="x", pady=6)
        self.dict_entry.focus_set()
        self.dict_result = tk.Label(f, text="", bg=C["bg"], font=("Arial", 12))
        self.dict_result.pack()
        tk.Button(f, text="✓ تحقق", command=self._check_dictation,
                  bg=C["accent"], fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=16, pady=9, cursor="hand2").pack(pady=8)

    def _check_dictation(self) -> None:
        if self.answered:
            return
        self.answered = True
        self.total_answered += 1
        correct_w = self.words[self.current_index].get("word", "").strip()
        user_ans = self.dict_var.get().strip()
        is_correct = (re.sub(r"[^a-zA-Z]", "", user_ans).lower() ==
                      re.sub(r"[^a-zA-Z]", "", correct_w).lower())
        self.dict_entry.config(state="disabled")
        if is_correct:
            self.dict_result.config(text=f"✅ ممتاز! الكلمة: {correct_w}", fg=C["green"])
        else:
            self.dict_result.config(text=f"❌ خطأ — الصواب: {correct_w}", fg=C["danger"])
        self._evaluate(is_correct)

    # ── ترتيب الكلمات ─────────────────────────────────────────────────────
    def _build_word_order(self, word: dict) -> None:
        ex = word.get("example", "") or f"She showed great {word.get('word', '')}."
        self._wo_correct = ex
        tokens = re.sub(r"[^\w\s]", "", ex).split()
        shuffled = tokens[:]
        while shuffled == tokens and len(tokens) > 1:
            random.shuffle(shuffled)

        self._wo_selected: list[str] = []
        self._wo_tokens = tokens
        self._wo_btns: dict[int, tk.Button] = {}

        outer = tk.Frame(self.ans_frame, bg=C["bg"])
        outer.pack(fill="both", expand=True)
        ans_f = tk.Frame(outer, bg=C["surface2"], padx=8, pady=8,
                         highlightbackground=C["border"], highlightthickness=1)
        ans_f.pack(fill="x", pady=(0, 12))
        self._wo_ans_lbl = tk.Label(ans_f, text="", bg=C["surface2"], fg=C["text"],
                                    font=("Consolas", 12), wraplength=580)
        self._wo_ans_lbl.pack(anchor="w")

        words_f = tk.Frame(outer, bg=C["bg"])
        words_f.pack(fill="x")
        for i, tok in enumerate(shuffled):
            btn = tk.Button(words_f, text=tok, bg=C["surface"], fg=C["text"],
                            font=("Consolas", 12), relief="flat", padx=10, pady=6,
                            cursor="hand2",
                            command=lambda t=tok, idx=i: self._wo_pick(t, idx))
            btn.pack(side="left", padx=4, pady=4)
            self._wo_btns[i] = btn

        ctrl = tk.Frame(outer, bg=C["bg"])
        ctrl.pack(fill="x", pady=(8, 0))
        tk.Button(ctrl, text="🗑 مسح", command=self._wo_reset,
                  bg=C["surface2"], fg=C["text2"], font=("Arial", 9),
                  relief="flat", padx=12, pady=6, cursor="hand2").pack(side="left", padx=4)
        tk.Button(ctrl, text="✓ تحقق", command=self._check_word_order,
                  bg=C["accent"], fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=16, pady=6, cursor="hand2").pack(side="left", padx=4)
        self._wo_result = tk.Label(outer, text="", bg=C["bg"], font=("Arial", 10))
        self._wo_result.pack(pady=(8, 0))

    def _wo_pick(self, token: str, idx: int) -> None:
        if self.answered:
            return
        btn = self._wo_btns[idx]
        if btn.cget("state") != "disabled":
            btn.config(state="disabled", bg=C["surface2"], fg=C["text3"])
            self._wo_selected.append(token)
            self._wo_ans_lbl.config(text=" ".join(self._wo_selected))

    def _wo_reset(self) -> None:
        if self.answered:
            return
        self._wo_selected.clear()
        self._wo_ans_lbl.config(text="")
        for btn in self._wo_btns.values():
            btn.config(state="normal", bg=C["surface"], fg=C["text"])

    def _check_word_order(self) -> None:
        if self.answered or not self._wo_selected:
            return
        self.answered = True
        self.total_answered += 1
        is_correct = self._wo_selected == self._wo_tokens
        for btn in self._wo_btns.values():
            btn.config(state="disabled")
        if is_correct:
            self._wo_result.config(text=f"✅ ممتاز! الجملة: {self._wo_correct}", fg=C["green"])
        else:
            self._wo_result.config(text=f"❌ الصواب: {self._wo_correct}", fg=C["danger"])
        self._evaluate(is_correct)

    # ── استماع ────────────────────────────────────────────────────────────
    def _build_listen(self, word: dict) -> None:
        self._build_mc(word)

    # ── ملء الفراغات ──────────────────────────────────────────────────────
    def _build_fill_blank(self, word: dict) -> None:
        correct_w = word.get("word", "")
        ex = word.get("example", "") or f"She showed great {correct_w}."
        blanked = re.sub(re.escape(correct_w), "_____", ex, count=1, flags=re.IGNORECASE)
        outer = tk.Frame(self.ans_frame, bg=C["bg"])
        outer.pack(fill="both", expand=True)
        tk.Label(outer, text=blanked, bg=C["surface2"], fg=C["text"],
                 font=("Georgia", 14), wraplength=560, justify="center",
                 padx=20, pady=14).pack(fill="x", pady=(0, 14))

        # FIX: يستخدم self._all_words (cached)
        distractors = [w for w in self._all_words if w.get("word", "") != correct_w]
        random.shuffle(distractors)
        options = [(correct_w, True)] + [(w.get("word", ""), False) for w in distractors[:3]]
        random.shuffle(options)
        self._fb_buttons = []
        for text, is_correct in options:
            btn = tk.Button(outer, text=f"  {text}", bg=C["surface"], fg=C["text"],
                            font=("Consolas", 13, "bold"), relief="flat", anchor="w",
                            padx=20, pady=10, cursor="hand2",
                            command=lambda t=text, c=is_correct: self._fb_answer(c, correct_w, ex))
            btn.pack(fill="x", pady=3)
            self._fb_buttons.append((btn, is_correct))

    def _fb_answer(self, is_correct: bool, correct_w: str, full_ex: str) -> None:
        if self.answered:
            return
        self.answered = True
        self.total_answered += 1
        for btn, correct in self._fb_buttons:
            btn.config(state="disabled", cursor="arrow")
            btn.config(bg=C["primary"] if correct else C["surface2"],
                       fg="white" if correct else C["text3"])
        self._evaluate(is_correct)

    # ── التقييم المشترك ────────────────────────────────────────────────────
    def _evaluate(self, is_correct: bool) -> None:
        word_entry = self.words[self.current_index]
        if is_correct:
            self.correct_count += 1
            self.app.sound.beep("correct")
            self.app.db.update_srs(word_entry["word"], 2)
            quality = 2
        else:
            self.app.sound.beep("wrong")
            self.app.db.update_srs(word_entry["word"], 0)
            quality = 0

        time_ms = int((time.time() - self._start_time) * 1000)
        try:
            self.app.db.log_review(word_entry["word"], quality, self.mode, time_ms)
        except Exception:
            pass
        self._show_next_btn()

    def _show_next_btn(self) -> None:
        f = tk.Frame(self.ans_frame, bg=C["bg"])
        f.pack(fill="x", pady=(10, 0))
        is_last = self.current_index + 1 >= len(self.words)
        tk.Button(f, text="🏁 عرض النتائج" if is_last else "التالي ⟶",
                  command=self._next_question,
                  bg=C["accent"], fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=24, pady=9, cursor="hand2").pack()

    def _next_question(self) -> None:
        self.current_index += 1
        self._load_question()

    def _speak_current(self) -> None:
        if self.current_index < len(self.words) and HAS_TTS:
            self.app.tts.speak_word(self.words[self.current_index].get("word", ""))

    def _on_enter(self) -> None:
        if self.mode == "write" and not self.answered:
            self._check_write()
        elif self.mode == "dictation" and not self.answered:
            self._check_dictation()
        elif self.answered:
            self._next_question()

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[\s\u200c\u200d]+", "", text).lower()

    # ── ملخص النتائج ──────────────────────────────────────────────────────
    def _show_summary(self) -> None:
        if not self.win:
            return
        accuracy = int(self.correct_count / self.total_answered * 100) if self.total_answered else 0
        self.app.xp.on_quiz_complete(accuracy, self.total_answered)
        self.app.challenge.update("quiz", self.correct_count)

        for w in self.win.winfo_children():
            w.destroy()
        f = tk.Frame(self.win, bg=C["bg"])
        f.pack(fill="both", expand=True, padx=30, pady=20)

        icon = "🏆" if accuracy >= 80 else "👍" if accuracy >= 60 else "📚"
        tk.Label(f, text=icon, bg=C["bg"], font=("Arial", 50)).pack(pady=(14, 0))
        tk.Label(f, text="انتهى الاختبار!", bg=C["bg"], fg=C["text"],
                 font=("Arial", 17, "bold")).pack(pady=8)

        g = tk.Frame(f, bg=C["surface"], padx=24, pady=16,
                     highlightbackground=C["border"], highlightthickness=1)
        g.pack(fill="x", pady=12)
        for label, value, color in [
            ("الأسئلة",  str(self.total_answered), C["blue"]),
            ("صحيح",     str(self.correct_count),  C["green"]),
            ("خطأ",      str(self.total_answered - self.correct_count), C["danger"]),
            ("النسبة",   f"{accuracy}%", C["green"] if accuracy >= 70 else C["warning"]),
        ]:
            row = tk.Frame(g, bg=C["surface"])
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, bg=C["surface"], fg=C["text2"],
                     font=("Arial", 11), width=12, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=C["surface"], fg=color,
                     font=("Consolas", 16, "bold")).pack(side="right")

        btns = tk.Frame(f, bg=C["bg"])
        btns.pack(pady=10)
        tk.Button(btns, text="🔄 اختبار جديد",
                  command=lambda: [self.win.destroy(), self.show()],
                  bg=C["primary"], fg="white", font=("Arial", 11, "bold"),
                  relief="flat", padx=20, pady=8, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btns, text="✖ إغلاق", command=self.win.destroy,
                  bg=C["surface2"], fg=C["text"], font=("Arial", 11),
                  relief="flat", padx=20, pady=8, cursor="hand2").pack(side="left", padx=6)
