# ui/dashboard.py
"""
لوحة التحكم الرئيسية — الشريط الجانبي + عرض الصفحات.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from config import C

if TYPE_CHECKING:
    from main import StudyAssistant

from ui.pages.home import HomePage
from ui.pages.review import ReviewPage
from ui.pages.words import WordsPage
from ui.pages.stats import StatsPage
from ui.pages.settings import SettingsPage
from ui.pages.youtube_page import YouTubePage
from ui.pages.weakness import WeaknessPage
from ui.pages.chatbot import ChatbotPage


class Dashboard:
    """النافذة الرئيسية للتطبيق."""

    NAV_ITEMS = [
        ("🏠  الرئيسية",   "home"),
        ("🃏  مراجعة",     "review"),
        ("📋  الكلمات",    "words"),
        ("🎬  YouTube",    "youtube"),
        ("🎯  نقاط الضعف", "weakness"),
        ("💬  Chatbot",    "chatbot"),
        ("📊  إحصائيات",   "stats"),
        ("⚙️  الإعدادات",  "settings"),
    ]

    def __init__(self, app: StudyAssistant) -> None:
        self.app = app
        self.win: tk.Toplevel | None = None
        self.pages: dict[str, tk.Frame] = {}
        self._job = None

    def show(self) -> None:
        if self.win and self.win.winfo_exists():
            self.win.deiconify()
            self.win.lift()
            return

        self.win = tk.Toplevel(self.app.root)
        self.win.title("مساعد المذاكرة v8.0")
        self.win.configure(bg=C["bg"])
        self.win.protocol("WM_DELETE_WINDOW", self._close)
        self.win.resizable(True, True)
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = 1000, 700
        self.win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.win.minsize(820, 560)

        self.app.root.withdraw()

        container = tk.Frame(self.win, bg=C["bg"])
        container.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(container, bg=C["surface"], width=200)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        self.main_area = tk.Frame(container, bg=C["bg"])
        self.main_area.pack(side="left", fill="both", expand=True)

        self.pages["home"]     = HomePage(self.main_area, self.app)
        self.pages["review"]   = ReviewPage(self.main_area, self.app)
        self.pages["words"]    = WordsPage(self.main_area, self.app)
        self.pages["youtube"]  = YouTubePage(self.main_area, self.app)
        self.pages["weakness"] = WeaknessPage(self.main_area, self.app)
        self.pages["chatbot"]  = ChatbotPage(self.main_area, self.app)
        self.pages["stats"]    = StatsPage(self.main_area, self.app)
        self.pages["settings"] = SettingsPage(self.main_area, self.app)

        self._show_page("home")

    def _build_sidebar(self) -> None:
        sb = self.sidebar
        tk.Label(sb, text="📖", bg=C["surface"], font=("Arial", 28)).pack(pady=(20, 0))
        tk.Label(sb, text="مساعد المذاكرة", bg=C["surface"],
                 fg=C["text"], font=("Arial", 10, "bold")).pack()
        tk.Label(sb, text="v8.0", bg=C["surface"],
                 fg=C["text3"], font=("Consolas", 8)).pack(pady=(0, 12))
        ttk.Separator(sb, orient="horizontal").pack(fill="x", padx=10)

        self.nav_buttons: list[tuple[tk.Button, str]] = []
        for text, page_id in self.NAV_ITEMS:
            btn = tk.Button(
                sb, text=text,
                command=lambda pid=page_id: self._show_page(pid),
                bg=C["surface"], fg=C["text2"],
                font=("Arial", 10), relief="flat",
                anchor="w", padx=16, pady=8, cursor="hand2",
                activebackground=C["surface2"], activeforeground=C["text"])
            btn.pack(fill="x")
            self.nav_buttons.append((btn, page_id))

        ttk.Separator(sb, orient="horizontal").pack(fill="x", padx=10, pady=8)

        tk.Button(sb, text="📌 مؤقت عائم",
                  command=self._toggle_floating,
                  bg=C["surface"], fg=C["text3"],
                  font=("Arial", 9), relief="flat",
                  anchor="w", padx=16, pady=6, cursor="hand2").pack(fill="x")

        ttk.Separator(sb, orient="horizontal").pack(fill="x", padx=10, pady=(4, 8))

        self.xp_label = tk.Label(sb, text="", bg=C["surface"], fg=C["yellow"],
                                 font=("Arial", 9, "bold"))
        self.xp_label.pack(anchor="w", padx=14)
        self.streak_label = tk.Label(sb, text="", bg=C["surface"], fg=C["text2"],
                                     font=("Arial", 9))
        self.streak_label.pack(anchor="w", padx=14, pady=(0, 4))

        self.words_label = tk.Label(sb, text="", bg=C["surface"], fg=C["text3"],
                                    font=("Arial", 8))
        self.words_label.pack(anchor="w", padx=14, pady=(0, 8))

        self._refresh()

    def _show_page(self, page_id: str) -> None:
        for pid, page in self.pages.items():
            if pid == page_id:
                page.pack(fill="both", expand=True)
            else:
                page.pack_forget()
        for btn, pid in self.nav_buttons:
            if pid == page_id:
                btn.config(bg=C["primary"], fg="white")
            else:
                btn.config(bg=C["surface"], fg=C["text2"])

    def _toggle_floating(self) -> None:
        try:
            self.app.floating_timer.toggle()
        except AttributeError:
            pass

    def _refresh(self) -> None:
        try:
            xp = self.app.xp
            level = xp.get_level()
            self.xp_label.config(text=f"{level[2]} {level[1]}")
            self.streak_label.config(text=f"🔥 {xp.get_streak()} يوم")
            total = self.app.db.count_words()
            self.words_label.config(text=f"📚 {total} كلمة")
        except Exception:
            pass
        if self.win and self.win.winfo_exists():
            self._job = self.win.after(2000, self._refresh)

    def _close(self) -> None:
        if self._job:
            try:
                self.win.after_cancel(self._job)
            except Exception:
                pass
        self.win.destroy()
        self.win = None
        self.app.root.quit()
