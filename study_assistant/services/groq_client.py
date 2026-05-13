# services/groq_client.py
"""
التكامل مع Groq API (بدون أي اعتماد على UI أو tkinter)
يقرأ المفتاح والإعدادات من قاعدة البيانات.
"""

from __future__ import annotations

import http.client
import json
import logging
import re
import ssl
from typing import Any, Optional

logger = logging.getLogger(__name__)

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]
DEFAULT_MODEL = GROQ_MODELS[0]


class GroqClient:
    """عميل Groq API بسيط ومستقل."""

    HOST = "api.groq.com"
    PATH = "/openai/v1/chat/completions"

    def __init__(self, db) -> None:
        self.db = db
        self._key: str = ""
        self._model: str = DEFAULT_MODEL
        self._ready: bool = False
        self._init_from_db()

    def _init_from_db(self) -> None:
        key = self.db.get_setting("GROQ_API_KEY", "").strip()
        if not key or len(key) < 20:
            return
        self._key = key
        self._model = self.db.get_setting("GROQ_MODEL", DEFAULT_MODEL)
        self._ready = True

    @property
    def is_ready(self) -> bool:
        return self._ready and bool(self._key)

    @property
    def model(self) -> str:
        return self._model

    def set_backup_key(self, key2: str) -> None:
        """حفظ المفتاح الاحتياطي للتبادل التلقائي عند حد الطلبات."""
        key2 = key2.strip()
        if key2 and len(key2) >= 20:
            self._backup_key = key2
            logger.info("Backup Groq key configured for rotation")

    def _call_with_rotation(self, prompt: str, timeout: int = 12) -> str:
        """استدعاء مع التبادل التلقائي للمفتاح عند فشل الأساسي."""
        try:
            return self._call(prompt, timeout)
        except Exception as e:
            backup = getattr(self, "_backup_key", "")
            if backup and "rate_limit" in str(e).lower():
                logger.warning("Primary key rate-limited, switching to backup")
                self._key, self._backup_key = backup, self._key
                return self._call(prompt, timeout)
            raise

    def set_key(self, key: str, model: str = DEFAULT_MODEL) -> bool:
        """يحفظ ويختبر مفتاح API جديد. يعيد True عند النجاح."""
        key = key.strip()
        if not key or len(key) < 20:
            return False
        self._key = key
        self._model = model or DEFAULT_MODEL
        self._ready = True
        try:
            resp = self._call("Say only: OK", timeout=8)
            if resp:
                self.db.set_setting("GROQ_API_KEY", key)
                self.db.set_setting("GROQ_MODEL", self._model)
                return True
        except Exception as e:
            logger.error(f"Groq key test failed: {e}")
        self._ready = False
        self._key = ""
        return False

    def _call(self, prompt: str, timeout: int = 12) -> str:
        """استدعاء API مباشر عبر HTTPS."""
        body = json.dumps({
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "max_tokens": 1200,
            "stream": False,
        }).encode("utf-8")

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(self.HOST, timeout=timeout, context=ctx)
        try:
            conn.request("POST", self.PATH,
                         body=body,
                         headers={
                             "Content-Type": "application/json; charset=utf-8",
                             "Authorization": f"Bearer {self._key}",
                             "Accept": "application/json",
                         })
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise RuntimeError(data["error"].get("message", str(data["error"])))
            return data["choices"][0]["message"]["content"]
        finally:
            conn.close()

    def enrich_word(self, word: str, translation: str) -> dict[str, Any]:
        """
        إثراء كلمة بمعلومات كاملة عبر Groq.
        يعود ببيانات افتراضية عند الفشل.
        """
        if not self.is_ready:
            return self._fallback(word, translation)

        prompt = (
            f'For the English word "{word}":\n'
            'Return ONLY a valid JSON object. No markdown, no code fences, no extra text.\n'
            '{\n'
            '  "ipa": "/phonetic/",\n'
            '  "type": "Noun|Verb|Adjective|Adverb",\n'
            '  "level": "A1|A2|B1|B2|C1|C2",\n'
            f'  "example": "natural English sentence using {word}",\n'
            '  "example_translation": "Arabic translation of the example",\n'
            '  "alt_translations": ["Arabic meaning 1","Arabic meaning 2","Arabic meaning 3"],\n'
            '  "synonyms": [{"word":"syn1","translation":"Arabic1"},{"word":"syn2","translation":"Arabic2"}],\n'
            '  "antonyms": [{"word":"ant1","translation":"Arabic1"},{"word":"ant2","translation":"Arabic2"}],\n'
            '  "sound_alikes": ["similar_word1","similar_word2","similar_word3"],\n'
            '  "related": [\n'
            '    {"word":"related1","translation":"Arabic1"},\n'
            '    {"word":"related2","translation":"Arabic2"},\n'
            '    {"word":"related3","translation":"Arabic3"}\n'
            '  ]\n'
            '}'
        )
        try:
            raw = self._call(prompt, timeout=15)
            raw = re.sub(r"```(?:json)?", "", raw).strip("`").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error(f"enrich_word failed for '{word}': {e}")
        return self._fallback(word, translation)

    def _fallback(self, word: str, translation: str) -> dict[str, Any]:
        """بيانات افتراضية عند تعذر Groq."""
        from deep_translator import GoogleTranslator
        example_en = f"She demonstrated great {word}."
        try:
            example_ar = GoogleTranslator(source="en", target="ar").translate(example_en)
        except Exception:
            example_ar = ""
        return {
            "ipa": "",
            "type": self._detect_type(word),
            "level": self._estimate_level(word),
            "example": example_en,
            "example_translation": example_ar,
            "alt_translations": [],
            "synonyms": [],
            "antonyms": [],
            "sound_alikes": [],
            "related": [],
        }

    @staticmethod
    def _detect_type(word: str) -> str:
        w = word.lower()
        if any(w.endswith(s) for s in ["tion","sion","ness","ity","ment","ance","ence","er","or","ist","ism"]):
            return "Noun"
        if any(w.endswith(s) for s in ["ous","ful","less","ive","al","ic","ble","ical","ary"]):
            return "Adjective"
        if any(w.endswith(s) for s in ["ate","ize","ise","ify","en","fy"]):
            return "Verb"
        if any(w.endswith(s) for s in ["ly","ward","wise"]):
            return "Adverb"
        return "Word"

    @staticmethod
    def _estimate_level(word: str) -> str:
        BASIC = {"the","be","to","of","and","a","in","that","have","it","for","not",
                 "on","with","he","you","do","at","this","but","his","by","from","they",
                 "we","say","her","she","or","an","will","my","one","all","would","there",
                 "their","what","so","up","out","if","about","who","get","which","go","me"}
        w = word.lower()
        if w in BASIC:     return "A1"
        if len(w) <= 5:    return "A2"
        if len(w) <= 7:    return "B1"
        if len(w) <= 9:    return "B2"
        if len(w) <= 11:   return "C1"
        return "C2"