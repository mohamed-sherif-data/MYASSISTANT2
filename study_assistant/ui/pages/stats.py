# ui/pages/stats.py
"""
صفحة الإحصائيات — Memory Graph + Heatmap + تقرير نقاط الضعف.
FIX: أسماء الأيام (weekday() 0=الإثنين → WEEKDAY_AR صحيحة).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta
from typing import TYPE_CHECKING

from config import C, WEEKDAY_AR

if TYPE_CHECKING:
    from main import StudyAssistant


class StatsPage(tk.Frame):
    def __init__(self, parent: tk.Widget, app: StudyAssistant) -> None:
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._build()

    def _build(self) -> None:
        canvas_outer = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas_outer.yview)
        self._scroll_frame = tk.Frame(canvas_outer, bg=C["bg"])
        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas_outer.configure(scrollregion=canvas_outer.bbox("all"))
        )
        canvas_outer.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas_outer.configure(yscrollcommand=vsb.set)
        canvas_outer.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        canvas_outer.bind("<MouseWheel>", lambda e: canvas_outer.yview_scroll(-1 * int(e.delta / 120), "units"))

        f = self._scroll_frame

        tk.Label(f, text="📊 إحصائيات الدراسة", bg=C["bg"], fg=C["text"],
                 font=("Arial", 15, "bold")).pack(anchor="w", padx=20, pady=16)

        # ── بطاقات الملخص ─────────────────────────────────────────────────
        cards_frame = tk.Frame(f, bg=C["bg"])
        cards_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.card_vals: list[tk.Label] = []
        for title in ["إجمالي الكلمات", "كلمات اليوم", "ساعات الأسبوع", "دقة المراجعة"]:
            card = tk.Frame(cards_frame, bg=C["card_bg"], padx=12, pady=10,
                            highlightbackground=C["border"], highlightthickness=1)
            card.pack(side="left", expand=True, fill="both", padx=3)
            tk.Label(card, text=title, bg=C["card_bg"], fg=C["text3"],
                     font=("Arial", 8)).pack()
            val = tk.Label(card, text="—", bg=C["card_bg"], fg=C["text"],
                           font=("Consolas", 20, "bold"))
            val.pack(pady=4)
            self.card_vals.append(val)

        # ── Heatmap (7 أيام) ───────────────────────────────────────────────
        tk.Label(f, text="نشاط آخر 7 أيام", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(8, 4))
        self.heatmap = tk.Frame(f, bg=C["bg"])
        self.heatmap.pack(fill="x", padx=20, pady=(0, 10))

        # ── Memory Graph ───────────────────────────────────────────────────
        tk.Label(f, text="📈 توزيع مستويات SRS", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(8, 4))
        self.graph_frame = tk.Frame(f, bg=C["card_bg"], padx=14, pady=10,
                                    highlightbackground=C["border"], highlightthickness=1)
        self.graph_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.graph_canvas = tk.Canvas(self.graph_frame, bg=C["card_bg"],
                                      height=120, highlightthickness=0)
        self.graph_canvas.pack(fill="x")

        # ── تقرير نقاط الضعف ──────────────────────────────────────────────
        tk.Label(f, text="🎯 تقرير نقاط الضعف", bg=C["bg"], fg=C["text2"],
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(8, 4))
        self.report_frame = tk.Frame(f, bg=C["surface"], padx=14, pady=10,
                                     highlightbackground=C["border"], highlightthickness=1)
        self.report_frame.pack(fill="x", padx=20, pady=(0, 14))
        self.report_lbl = tk.Label(self.report_frame, text="", bg=C["surface"],
                                   fg=C["text2"], font=("Consolas", 9),
                                   anchor="w", justify="left")
        self.report_lbl.pack(anchor="w")

        self._refresh()

    def _refresh(self) -> None:
        db = self.app.db
        words = db.load_words()
        today = date.today().isoformat()

        total_words = len(words)
        today_stats = db.get_daily_stats(today)
        today_words = today_stats.get("words_added", 0)

        weekly_minutes = 0
        for i in range(7):
            day = (date.today() - timedelta(days=i)).isoformat()
            weekly_minutes += db.get_daily_stats(day).get("minutes", 0)
        wh, wm = weekly_minutes // 60, weekly_minutes % 60
        weekly_str = f"{wh}س {wm}د" if wh > 0 else f"{wm}د"

        tr = sum(int(w.get("total_reviews", 0) or 0) for w in words)
        cr = sum(int(w.get("correct_reviews", 0) or 0) for w in words)
        accuracy = f"{int(cr / tr * 100)}%" if tr > 0 else "—"

        self.card_vals[0].config(text=str(total_words))
        self.card_vals[1].config(text=str(today_words))
        self.card_vals[2].config(text=weekly_str)
        self.card_vals[3].config(text=accuracy)

        self._draw_heatmap(db)
        self._draw_memory_graph(words)

        try:
            report = db.get_weakness_report()
            self.report_lbl.config(text=report)
        except Exception:
            self.report_lbl.config(text="لا توجد بيانات مراجعة بعد.")

        self.after(10000, self._refresh)

    def _draw_heatmap(self, db) -> None:
        for w in self.heatmap.winfo_children():
            w.destroy()

        days = [(date.today() - timedelta(days=6 - i)) for i in range(7)]
        day_mins = [db.get_daily_stats(d.isoformat()).get("minutes", 0) for d in days]
        max_mins = max(day_mins + [1])

        for i, d in enumerate(days):
            mins = day_mins[i]
            pct = mins / max_mins
            intensity = int(30 + pct * 200)
            color = f"#{0:02x}{intensity:02x}{0:02x}" if mins > 0 else C["surface2"]

            col = tk.Frame(self.heatmap, bg=C["bg"])
            col.pack(side="left", expand=True, fill="x", padx=2)

            box = tk.Frame(col, bg=color,
                           highlightbackground=C["border"], highlightthickness=1)
            box.pack(fill="x")
            lbl_min = tk.Label(box, text=f"{mins}د" if mins > 0 else "—",
                               bg=color, fg=C["bg"] if mins > 60 else C["text"],
                               font=("Arial", 7))
            lbl_min.pack(ipady=12)

            # FIX: weekday() 0=الإثنين → WEEKDAY_AR صحيحة
            day_name = WEEKDAY_AR[d.weekday()]
            tk.Label(col, text=day_name, bg=C["bg"], fg=C["text3"],
                     font=("Arial", 7)).pack()
            if d.isoformat() == date.today().isoformat():
                tk.Label(col, text="●", bg=C["bg"], fg=C["accent"],
                         font=("Arial", 7)).pack()

    def _draw_memory_graph(self, words: list[dict]) -> None:
        """رسم توزيع مستويات SRS كـ bar chart بسيط."""
        self.graph_canvas.delete("all")

        srs_counts = [0] * 7
        for w in words:
            lvl = min(int(w.get("srs_level", 0) or 0), 6)
            srs_counts[lvl] += 1

        total = len(words) or 1
        self.graph_canvas.update_idletasks()
        W = self.graph_canvas.winfo_width() or 500
        H = 110
        bar_w = max((W - 60) // 7 - 8, 20)
        max_count = max(srs_counts + [1])
        colors = [C["danger"], C["warning"], C["yellow"],
                  C["green"], C["teal"], C["accent"], C["purple"]]
        labels = ["0", "1", "2", "3", "4", "5", "6+"]

        for i, count in enumerate(srs_counts):
            x = 30 + i * ((W - 60) // 7)
            bar_h = int((count / max_count) * (H - 30))
            y0 = H - 20 - bar_h
            y1 = H - 20
            self.graph_canvas.create_rectangle(x, y0, x + bar_w, y1,
                                               fill=colors[i], outline="")
            if count > 0:
                self.graph_canvas.create_text(x + bar_w // 2, y0 - 4,
                                              text=str(count), fill=C["text"],
                                              font=("Arial", 7))
            self.graph_canvas.create_text(x + bar_w // 2, H - 8,
                                          text=f"★{labels[i]}", fill=C["text3"],
                                          font=("Arial", 7))
