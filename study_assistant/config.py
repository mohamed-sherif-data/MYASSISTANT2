# config.py
"""
إعدادات التطبيق المركزية — ألوان، خطوط، مسارات.
"""

from pathlib import Path

# ── المسارات ──────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
NOTES_DIR    = BASE_DIR / "StudyNotes"
CONFIG_ENV   = BASE_DIR / "config.env"

# ── ألوان Dark Theme (GitHub-inspired) ──────────────────────────────────
C: dict[str, str] = {
    "bg":        "#0d1117",
    "surface":   "#161b22",
    "surface2":  "#21262d",
    "border":    "#30363d",
    "primary":   "#238636",
    "primary_h": "#2ea043",
    "accent":    "#1f6feb",
    "accent_h":  "#388bfd",
    "danger":    "#da3633",
    "warning":   "#e3b341",
    "text":      "#e6edf3",
    "text2":     "#8b949e",
    "text3":     "#484f58",
    "green":     "#3fb950",
    "yellow":    "#d29922",
    "blue":      "#58a6ff",
    "purple":    "#bc8cff",
    "card_bg":   "#1c2128",
    "work":      "#238636",
    "brk":       "#e3b341",
    "teal":      "#39d353",
    "orange":    "#f0883e",
}

# ── الخطوط المركزية ───────────────────────────────────────────────────────
FONTS: dict[str, tuple] = {
    "title":    ("Arial",   15, "bold"),
    "subtitle": ("Arial",   11, "bold"),
    "body":     ("Arial",   10),
    "small":    ("Arial",    8),
    "mono":     ("Consolas", 10),
    "mono_lg":  ("Consolas", 20, "bold"),
    "word":     ("Georgia",  32, "bold"),
    "word_sm":  ("Georgia",  16, "bold"),
    "ipa":      ("Arial",    11, "italic"),
    "label":    ("Arial",     9),
    "btn":      ("Arial",    10, "bold"),
}

# ── مسافات موحدة ─────────────────────────────────────────────────────────
PAD = {"page": 20, "card": 14, "btn_x": 14, "btn_y": 7}

# ألوان مستويات CEFR
LEVEL_COLORS: dict[str, str] = {
    "A1": C["green"],  "A2": C["green"],
    "B1": C["yellow"], "B2": C["yellow"],
    "C1": "#f78166",   "C2": "#f78166",
}

# قائمة المواد الافتراضية
DEFAULT_SUBJECTS: list[str] = [
    "بدون مادة", "IS", "C#", "Technical Writing",
    "Scientific Thinking", "Electronics", "Logic", "Math2",
]

# أسماء أيام الأسبوع (weekday() 0=Monday)
WEEKDAY_AR = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
