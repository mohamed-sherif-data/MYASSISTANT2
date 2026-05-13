# services/translator.py
"""
TranslationManager: ترجمة الكلمات المنسوخة، إثرائها، حفظها، وتشغيل الأصوات.
لا يعتمد على tkinter. لعرض Toast سنستخدم callback اختياري.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date
from typing import Any, Callable, Optional

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)


class TranslationManager:
    """معالجة كلمة من الحافظة: ترجمة ← Groq ← حفظ ← نطق."""

    def __init__(self, db, groq: Any, tts: Any, sound: Any,
                 get_subject: Callable[[], str]) -> None:
        self.db = db
        self.groq = groq
        self.tts = tts
        self.sound = sound
        self.get_subject = get_subject
        self.toast_callback: Optional[Callable[[str, dict], None]] = None

    def set_toast_callback(self, cb: Callable[[str, dict], None]) -> None:
        """دالة اختيارية لعرض Toast في الـ UI."""
        self.toast_callback = cb

    @staticmethod
    def _is_valid_word(text: str) -> bool:
        t = text.strip()
        if not t or len(t) > 40 or len(t.split()) > 5:
            return False
        if any(x in t.lower() for x in ["http", "www."]):
            return False
        if "\n" in t or "\r" in t:
            return False
        if not any(ord(c) < 128 and c.isalpha() for c in t):
            return False
        return True

    @staticmethod
    def _translate(text: str, src: str = "en", tgt: str = "ar") -> str:
        try:
            return GoogleTranslator(source=src, target=tgt).translate(text) or ""
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return ""

    def process_word(self) -> None:
        """تشغيل معالجة الكلمة من الحافظة (في خيط منفصل)."""
        def _worker():
            try:
                import pyperclip
                raw = pyperclip.paste()
                if not raw or not self._is_valid_word(raw.strip()):
                    return
                text = raw.strip()

                if self.db.word_exists(text):
                    self.sound.beep("normal")
                    return

                translation = self._translate(text)
                if not translation:
                    self.sound.beep("error")
                    return

                enriched = self.groq.enrich_word(text, translation)
                alts = [a for a in enriched.get("alt_translations", []) if a and a != translation]
                subject = self.get_subject() or ""

                entry = {
                    "Word": text,
                    "Translation": translation,
                    "Alt_Translations": json.dumps(alts, ensure_ascii=False),
                    "IPA": enriched.get("ipa", ""),
                    "Type": enriched.get("type", "Word"),
                    "Level": enriched.get("level", "B1"),
                    "Example": enriched.get("example", ""),
                    "Example_Translation": enriched.get("example_translation", ""),
                    "Related_Words": json.dumps(enriched.get("related", []), ensure_ascii=False),
                    "Synonyms": json.dumps(enriched.get("synonyms", []), ensure_ascii=False),
                    "Antonyms": json.dumps(enriched.get("antonyms", []), ensure_ascii=False),
                    "Sound_Alikes": json.dumps(enriched.get("sound_alikes", []), ensure_ascii=False),
                    "SRS_Level": 0,
                    "Next_Review": date.today().isoformat(),
                    "Total_Reviews": 0,
                    "Correct_Reviews": 0,
                    "Subject": subject,
                    "Added_Date": date.today().isoformat(),
                }

                if self.db.add_word(entry):
                    self.sound.beep("save")
                    self.db.log_word_added()
                    if self.toast_callback:
                        toast_data = {**enriched, "translation": translation, "alt_translations": alts}
                        self.toast_callback(text, toast_data)
                    logger.info(f"Saved: {text} [{enriched.get('type')}/{enriched.get('level')}]")
                    self.tts.speak_word_then_example(text, enriched.get("example", ""))
                else:
                    self.sound.beep("normal")
            except Exception as e:
                logger.error(f"process_word: {e}")

        threading.Thread(target=_worker, daemon=True).start()