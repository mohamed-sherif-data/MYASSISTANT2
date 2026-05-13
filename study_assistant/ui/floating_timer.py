# ui/floating_timer.py
"""
الساعة الطائرة (PiP) — نافذة صغيرة عائمة تعرض وقت البومودورو.
تعتمد على PomodoroTimer من core مباشرة.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from config import C

if TYPE_CHECKING:
    from core.pomodoro import PomodoroTimer


class FloatingTimer:
    """نافذة PiP صغيرة (148×96 عادي، 148×28 مضغوط)."""

    FULL_W = 148
    FULL_H = 96
    COMPACT_W = 148
    COMPACT_H = 28

    def __init__(self, pomodoro: PomodoroTimer) -> None:
        self.pomodoro = pomodoro
        self.win: tk.Toplevel | None = None
        self._compact = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._last_x: int | None = None
        self._last_y: int | None = None

    # ── إظهار / إخفاء ─────────────────────────────────────────────────
    def show(self) -> None:
        if self.win and self.win.winfo_exists():
            self.win.lift()
            return

        self.win = tk.Toplevel()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.92)
        self.win.configure(bg=C["surface"])

        sw = self.win.winfo_screenwidth()
        x = self._last_x if self._last_x is not None else sw - self.FULL_W - 14
        y = self._last_y if self._last_y is not None else 12
        self.win.geometry(f"{self.FULL_W}x{self.FULL_H}+{x}+{y}")

        self._build_ui()
        self._tick()

    def hide(self) -> None:
        if self.win and self.win.winfo_exists():
            self._last_x = self.win.winfo_x()
            self._last_y = self.win.winfo_y()
            self.win.destroy()
        self.win = None

    def toggle(self) -> None:
        if self.win and self.win.winfo_exists():
            self.hide()
        else:
            self.show()

    # ── بناء الواجهة ──────────────────────────────────────────────────
    def _build_ui(self) -> None:
        for w in self.win.winfo_children():
            w.destroy()

        frm = tk.Frame(self.win, bg=C["surface"],
                       highlightbackground=C["border"], highlightthickness=1)
        frm.pack(fill="both", expand=True)

        # شريط العنوان (قابل للسحب)
        bar = tk.Frame(frm, bg=C["surface2"], pady=1)
        bar.pack(fill="x")
        self._title_lbl = tk.Label(bar, text="Pomodoro", bg=C["surface2"],
                                   fg=C["text3"], font=("Arial", 7))
        self._title_lbl.pack(side="left", padx=(5, 2))

        # زر التبديل إلى الوضع المضغوط
        self._btn_toggle = tk.Button(bar, text="▲", command=self._toggle_compact,
                                     bg=C["surface2"], fg=C["text3"],
                                     font=("Arial", 7), relief="flat", padx=3,
                                     cursor="hand2")
        self._btn_toggle.pack(side="right", padx=(0, 2))
        tk.Button(bar, text="✕", command=self.hide,
                  bg=C["surface2"], fg=C["text3"],
                  font=("Arial", 7), relief="flat", padx=3,
                  cursor="hand2").pack(side="right")

        for widget in (bar, self._title_lbl):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        # الوقت
        self._lbl_time = tk.Label(frm, text="--:--", bg=C["surface"],
                                  fg=C["text"], font=("Consolas", 28, "bold"))
        self._lbl_time.pack(pady=(2, 0))

        # التفاصيل (تُخفى في الوضع المضغوط)
        self._details = tk.Frame(frm, bg=C["surface"])
        self._lbl_phase = tk.Label(self._details, text="متوقف", bg=C["surface"],
                                   fg=C["text3"], font=("Arial", 8))
        self._lbl_phase.pack()

        ctrl = tk.Frame(self._details, bg=C["surface"])
        ctrl.pack(pady=(2, 4))
        for sym, cmd, clr in [
            ("▶", self.pomodoro.start, C["primary"]),
            ("⏸", self.pomodoro.pause, C["warning"]),
            ("⏹", self.pomodoro.stop,  C["danger"]),
        ]:
            tk.Button(ctrl, text=sym, command=cmd, bg=clr, fg="white",
                      font=("Arial", 9), relief="flat", width=2,
                      cursor="hand2").pack(side="left", padx=1)

        self._apply_compact(animated=False)

    # ─ـ السحب ─────────────────────────────────────────────────────────
    def _drag_start(self, event: tk.Event) -> None:
        self._drag_offset_x = event.x_root - self.win.winfo_x()
        self._drag_offset_y = event.y_root - self.win.winfo_y()

    def _drag_move(self, event: tk.Event) -> None:
        nx = event.x_root - self._drag_offset_x
        ny = event.y_root - self._drag_offset_y
        self._last_x, self._last_y = nx, ny
        self.win.geometry(f"+{nx}+{ny}")

    # ─ـ الوضع المضغوط ────────────────────────────────────────────────
    def _toggle_compact(self) -> None:
        self._compact = not self._compact
        self._apply_compact(animated=True)

    def _apply_compact(self, animated: bool = False) -> None:
        if not (self.win and self.win.winfo_exists()):
            return
        if self._compact:
            self._details.pack_forget()
            self._lbl_time.config(font=("Consolas", 14, "bold"))
            self.win.geometry(f"{self.COMPACT_W}x{self.COMPACT_H}")
            self._btn_toggle.config(text="▼")
        else:
            self._lbl_time.config(font=("Consolas", 28, "bold"))
            self._details.pack(fill="x")
            self.win.geometry(f"{self.FULL_W}x{self.FULL_H}")
            self._btn_toggle.config(text="▲")

    # ─ـ التحديث كل ثانية ──────────────────────────────────────────────
    def _tick(self) -> None:
        if not (self.win and self.win.winfo_exists()):
            return

        color_map = {
            "work":        C["green"],
            "short_break": C["yellow"],
            "long_break":  C["yellow"],
            "idle":        C["text3"],
        }
        clr = color_map.get(self.pomodoro.phase, C["text3"])

        self._lbl_time.config(text=self.pomodoro.time_str(), fg=clr)
        self._lbl_phase.config(text=self.pomodoro.status_label(), fg=clr)

        if self._compact:
            self._title_lbl.config(text=self.pomodoro.status_label())

        self.win.after(1000, self._tick)