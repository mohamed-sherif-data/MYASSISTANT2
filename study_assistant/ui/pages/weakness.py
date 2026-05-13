# ui/pages/weakness.py
"""
صفحة نقاط الضعف — تحليل أداء المراجعة بالبيانات الموجودة في قاعدة البيانات.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from config import C

if TYPE_CHECKING:
    from main import StudyAssistant


class WeaknessPage(tk.Frame):
    def __init__(self, parent: tk.Widget, app: StudyAssistant) -> None:
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self) -> None:
        canvas_outer = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas_outer.yview)
        self._sf = tk.Frame(canvas_outer, bg=C["bg"])
        self._sf.bind("<Configure>",
                      lambda e: canvas_outer.configure(
                          scrollregion=canvas_outer.bbox("all")))
        canvas_outer.create_window((0, 0), window=self._sf, anchor="nw")
        canvas_outer.configure(yscrollcommand=vsb.set)
        canvas_outer.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        f = self._sf
        hdr = tk.Frame(f, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=14)
        tk.Label(hdr, text="🎯 تحليل نقاط الضعف", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(side="left")
        tk.Button(hdr, text="🔄 تحديث", command=self._refresh,
                  bg=C["surface2"], fg=C["text2"], font=("Arial", 9),
                  relief="flat", padx=10, pady=4, cursor="hand2").pack(side="right")

        # ── بطاقات ملخص ────────────────────────────────────────────────────
        cards = tk.Frame(f, bg=C["bg"])
        cards.pack(fill="x", padx=20, pady=(0, 12))
        self._card_vals: list[tk.Label] = []
        for title, color in [
            ("إجمالي المراجعات", C["blue"]),
            ("الأخطاء",          C["danger"]),
            ("نسبة الخطأ",       C["warning"]),
            ("متوسط وقت الإجابة", C["purple"]),
        ]:
            card = tk.Frame(cards, bg=C["card_bg"], padx=12, pady=10,
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", expand=True, fill="both", padx=3)
            tk.Label(card, text=title, bg=C["card_bg"], fg=C["text3"],
                     font=("Arial", 8)).pack()
            val = tk.Label(card, text="—", bg=C["card_bg"], fg=color,
                           font=("Consolas", 18, "bold"))
            val.pack(pady=4)
            self._card_vals.append(val)

        # ── الكلمات الضعيفة ────────────────────────────────────────────────
        tk.Label(f, text="📋 الكلمات التي تحتاج مراجعة إضافية", bg=C["bg"],
                 fg=C["text2"], font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(4, 4))
        self._weak_frame = tk.Frame(f, bg=C["surface"],
                                    highlightbackground=C["border"], highlightthickness=1)
        self._weak_frame.pack(fill="x", padx=20, pady=(0, 12))
        self._weak_lbl = tk.Label(self._weak_frame, text="لا توجد بيانات بعد",
                                  bg=C["surface"], fg=C["text3"],
                                  font=("Arial", 9), pady=10, padx=12)
        self._weak_lbl.pack(anchor="w")

        # ── الأداء حسب نوع الاختبار ──────────────────────────────────────
        tk.Label(f, text="📊 الأداء حسب نوع الاختبار", bg=C["bg"],
                 fg=C["text2"], font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(4, 4))
        self._mode_frame = tk.Frame(f, bg=C["surface"],
                                    highlightbackground=C["border"], highlightthickness=1)
        self._mode_frame.pack(fill="x", padx=20, pady=(0, 12))

        # ── الأداء حسب المستوى ─────────────────────────────────────────────
        tk.Label(f, text="📈 الأداء حسب مستوى CEFR", bg=C["bg"],
                 fg=C["text2"], font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(4, 4))
        self._level_canvas = tk.Canvas(f, bg=C["card_bg"], height=120,
                                       highlightbackground=C["border"], highlightthickness=1)
        self._level_canvas.pack(fill="x", padx=20, pady=(0, 12))

        # ── التوصية ─────────────────────────────────────────────────────────
        tk.Label(f, text="💡 التوصية", bg=C["bg"],
                 fg=C["text2"], font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(4, 4))
        self._rec_frame = tk.Frame(f, bg=C["surface"], padx=14, pady=12,
                                   highlightbackground=C["border"], highlightthickness=1)
        self._rec_frame.pack(fill="x", padx=20, pady=(0, 14))
        self._rec_lbl = tk.Label(self._rec_frame, text="",
                                 bg=C["surface"], fg=C["text2"],
                                 font=("Arial", 10), anchor="w", justify="left",
                                 wraplength=700)
        self._rec_lbl.pack(anchor="w")

        self._refresh()

    def _refresh(self) -> None:
        try:
            data = self.app.db.get_weakness_analysis(30)
        except Exception:
            return

        # بطاقات الملخص
        mode_data = data.get("mode_errors", {})
        total = sum(v.get("total", 0) for v in mode_data.values())
        errors = sum(v.get("errors", 0) for v in mode_data.values())
        pct = f"{int(errors/total*100)}%" if total else "—"
        avg_ms = data.get("avg_time_ms", 0)
        avg_s = f"{avg_ms/1000:.1f}ث" if avg_ms else "—"

        self._card_vals[0].config(text=str(total))
        self._card_vals[1].config(text=str(errors))
        self._card_vals[2].config(text=pct)
        self._card_vals[3].config(text=avg_s)

        # الكلمات الضعيفة
        for w in self._weak_frame.winfo_children():
            w.destroy()
        weak = data.get("weak_words", [])
        if weak:
            for wd in weak[:8]:
                row = tk.Frame(self._weak_frame, bg=C["surface"])
                row.pack(fill="x", padx=8, pady=1)
                pct_w = int(wd["errors"] / max(wd["attempts"], 1) * 100)
                color = C["danger"] if pct_w >= 60 else C["warning"]
                tk.Label(row, text=wd["word"], bg=C["surface"], fg=C["text"],
                         font=("Consolas", 10, "bold"), width=18, anchor="w").pack(side="left")
                tk.Label(row, text=f"❌ {wd['errors']} / {wd['attempts']}",
                         bg=C["surface"], fg=color, font=("Arial", 9)).pack(side="left", padx=8)
                # شريط التقدم
                bar_outer = tk.Frame(row, bg=C["surface2"], height=8, width=160)
                bar_outer.pack(side="left", padx=4)
                bar_outer.pack_propagate(False)
                bar_inner = tk.Frame(bar_outer, bg=color,
                                     height=8, width=int(pct_w * 1.6))
                bar_inner.place(x=0, y=0)
                tk.Label(row, text=f"{pct_w}%", bg=C["surface"],
                         fg=color, font=("Arial", 9)).pack(side="left")
        else:
            tk.Label(self._weak_frame, text="✅ لا توجد كلمات ضعيفة بعد — استمر في المراجعة!",
                     bg=C["surface"], fg=C["green"],
                     font=("Arial", 9), pady=10, padx=12).pack(anchor="w")

        # الأداء حسب نوع الاختبار
        for w in self._mode_frame.winfo_children():
            w.destroy()
        if mode_data:
            mode_names = {
                "mc_en_ar": "اختيار متعدد",
                "mc_ar_en": "عكسي",
                "write":    "كتابة",
                "dictation":"إملاء",
                "listen":   "استماع",
                "word_order":"ترتيب",
                "fill_blank":"فراغات",
                "flashcard":"بطاقات",
            }
            for mode, mdata in sorted(mode_data.items(),
                                      key=lambda x: x[1].get("errors", 0),
                                      reverse=True)[:6]:
                mt = mdata.get("total", 0) or 1
                me = mdata.get("errors", 0)
                mp = int(me / mt * 100)
                color = C["danger"] if mp >= 50 else C["warning"] if mp >= 30 else C["green"]
                row = tk.Frame(self._mode_frame, bg=C["surface"])
                row.pack(fill="x", padx=8, pady=2)
                tk.Label(row, text=mode_names.get(mode, mode),
                         bg=C["surface"], fg=C["text"],
                         font=("Arial", 9), width=14, anchor="w").pack(side="left")
                tk.Label(row, text=f"{mp}% خطأ ({me}/{mt})",
                         bg=C["surface"], fg=color,
                         font=("Arial", 9)).pack(side="left", padx=8)
        else:
            tk.Label(self._mode_frame, text="لا توجد بيانات بعد — ابدأ بالمراجعة!",
                     bg=C["surface"], fg=C["text3"],
                     font=("Arial", 9), pady=8, padx=12).pack(anchor="w")

        # رسم مستويات CEFR
        self._draw_level_chart(data.get("level_errors", {}))

        # التوصية
        try:
            rec = self.app.db._get_recommendation(data)
            self._rec_lbl.config(text=rec or "استمر في المراجعة المنتظمة للحصول على توصيات.")
        except Exception:
            self._rec_lbl.config(text="استمر في المراجعة المنتظمة.")

    def _draw_level_chart(self, level_data: dict) -> None:
        self._level_canvas.delete("all")
        levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
        colors = [C["green"], C["green"], C["yellow"], C["yellow"], C["danger"], C["danger"]]

        self._level_canvas.update_idletasks()
        W = self._level_canvas.winfo_width() or 600
        H = 110
        bar_w = max((W - 40) // 6 - 10, 30)
        max_total = max((d.get("total", 0) for d in level_data.values()), default=1) or 1

        for i, lvl in enumerate(levels):
            d = level_data.get(lvl, {"total": 0, "errors": 0})
            total = d.get("total", 0)
            errors = d.get("errors", 0)
            x = 20 + i * ((W - 40) // 6)

            if total > 0:
                bar_h = int((total / max_total) * (H - 35))
                err_h = int((errors / max_total) * (H - 35))
                y0 = H - 20 - bar_h
                self._level_canvas.create_rectangle(
                    x, y0, x + bar_w, H - 20,
                    fill=C["surface2"], outline="")
                if err_h > 0:
                    self._level_canvas.create_rectangle(
                        x, H - 20 - err_h, x + bar_w, H - 20,
                        fill=colors[i], outline="")
                pct = int(errors / total * 100)
                self._level_canvas.create_text(
                    x + bar_w // 2, y0 - 4,
                    text=f"{pct}%", fill=C["text"], font=("Arial", 7))

            self._level_canvas.create_text(
                x + bar_w // 2, H - 8,
                text=lvl, fill=C["text3"], font=("Arial", 8, "bold"))
