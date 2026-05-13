# services/pdf_manager.py
"""
PDFManager مستقل لإنشاء ودمج ملفات PDF.
لا يعتمد على tkinter أو SoundManager مباشرة.
"""

from __future__ import annotations

import logging
import os
import platform
import tempfile
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from fpdf import FPDF
from PIL import Image
import PyPDF2
import pyperclip

logger = logging.getLogger(__name__)
_SYSTEM = platform.system()


def _get_unicode_font() -> tuple[str, str]:
    """إيجاد خط Unicode متاح على النظام الحالي."""
    candidates = []
    if _SYSTEM == "Windows":
        candidates = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\calibri.ttf",
        ]
    elif _SYSTEM == "Darwin":
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path, "UniFont"
    return "", ""


class PDFManager:
    """إنشاء PDF من نصوص وصور، وحفظ المحاضرات في مجلدات منظمة."""

    def __init__(self, notes_dir: Path, sound: Optional[object] = None) -> None:
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(exist_ok=True)
        self.current_path: Optional[Path] = None
        self._sound = sound
        self._font_path, self._font_name = _get_unicode_font()

    def set_lecture(self, subject: str, num: int) -> None:
        if subject and subject != "بدون مادة":
            lecture_dir = self.notes_dir / subject
            lecture_dir.mkdir(exist_ok=True)
            self.current_path = lecture_dir / f"Lecture_{num:02d}.pdf"
        else:
            self.current_path = self.notes_dir / f"General_{date.today().isoformat()}.pdf"

    def _make_pdf(self) -> FPDF:
        pdf = FPDF()
        pdf.set_margins(5, 5, 5)
        pdf.add_page()
        if self._font_path:
            try:
                pdf.add_font(self._font_name, "", self._font_path, uni=True)
                pdf.set_font(self._font_name, size=12)
                return pdf
            except Exception:
                pass
        pdf.set_font("Helvetica", size=12)
        return pdf

    def _make_text_pdf(self, text: str) -> str:
        pdf = self._make_pdf()
        page_w = pdf.w - 10
        pdf.set_font_size(9)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(page_w, 6, f"Saved: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.ln(2)
        pdf.set_font_size(12)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(page_w, 7, text)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
        pdf.output(tmp)
        return tmp

    def _make_image_pdf(self, img: Image.Image) -> str:
        pdf = FPDF()
        pdf.set_margins(5, 5, 5)
        pdf.add_page()
        tmp_img = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        img.save(tmp_img)
        pw, ph = pdf.w - 10, pdf.h - 10
        ratio = min(pw / img.width, ph / img.height)
        pdf.image(tmp_img, 5, 5, img.width * ratio, img.height * ratio)
        os.remove(tmp_img)
        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
        pdf.output(tmp)
        return tmp

    def _merge_pdfs(self, base_path: str, new_path: str) -> None:
        import shutil
        if os.path.exists(base_path):
            merger = PyPDF2.PdfMerger()
            merger.append(base_path)
            merger.append(new_path)
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False).name
            merger.write(tmp)
            merger.close()
            shutil.move(tmp, base_path)
        else:
            shutil.move(new_path, base_path)
        if os.path.exists(new_path):
            os.remove(new_path)

    def save_clipboard(self) -> bool:
        if not self.current_path:
            self.current_path = self.notes_dir / f"General_{date.today().isoformat()}.pdf"
        try:
            if _SYSTEM == "Windows":
                from PIL import ImageGrab
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image):
                    self._merge_pdfs(str(self.current_path), self._make_image_pdf(img))
                    if self._sound:
                        self._sound.beep("note")
                    return True

            text = pyperclip.paste()
            if text and text.strip():
                self._merge_pdfs(str(self.current_path), self._make_text_pdf(text.strip()))
                if self._sound:
                    self._sound.beep("note")
                return True
        except Exception as e:
            logger.error(f"PDF save clipboard: {e}")
        return False

    def add_summary(self, subject: str, lecture: int, cycles: int, minutes: int) -> None:
        if not self.current_path:
            return
        text = (
            f"\n{'='*40}\n       SESSION SUMMARY\n{'='*40}\n"
            f"Date:     {datetime.now().strftime('%Y-%m-%d')}\n"
            f"Time:     {datetime.now().strftime('%H:%M')}\n"
            f"Subject:  {subject}\nLecture:  #{lecture}\n"
            f"Cycles:   {cycles}\nWork:     {minutes} min\n{'='*40}\n"
        )
        self._merge_pdfs(str(self.current_path), self._make_text_pdf(text))
