# services/sentence_builder.py
"""
AI Sentence Builder - توليد جمل وقصص وحوارات وتمارين باستخدام كلمات المستخدم.
"""

from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SentenceBuilder:
    """توليد تمارين بالذكاء الاصطناعي."""

    def __init__(self, groq_client: Any) -> None:
        self.groq = groq_client

    def generate_story(self, words: list[str], lang: str = "ar") -> str:
        """توليد قصة قصيرة باستخدام الكلمات."""
        if not words or not self.groq.is_ready:
            return self._fallback_story(words)

        word_list = ", ".join(words[:8])
        prompt = (
            f"Create a short story (3-5 sentences) in English using these vocabulary words: {word_list}\n"
            "The story should be simple and natural. Then translate it to Arabic.\n"
            "Format:\n"
            "ENGLISH:\n<story in English>\n\n"
            "ARABIC:\n<translation>"
        )
        try:
            return self.groq._call(prompt, timeout=20)
        except Exception as e:
            logger.error(f"Story generation: {e}")
            return self._fallback_story(words)

    def generate_dialogue(self, words: list[str]) -> str:
        """توليد حوار باستخدام الكلمات."""
        if not words or not self.groq.is_ready:
            return self._fallback_dialogue(words)

        word_list = ", ".join(words[:6])
        prompt = (
            f"Create a short dialogue (6-8 lines) between two people using these words: {word_list}\n"
            "Format:\n"
            "A: English line\n"
            "B: English line\n"
            "(alternating, then add Arabic translation below)\n\n"
            "ARABIC TRANSLATION:\n<translate each line>"
        )
        try:
            return self.groq._call(prompt, timeout=15)
        except Exception as e:
            logger.error(f"Dialogue generation: {e}")
            return self._fallback_dialogue(words)

    def generate_exercises(self, words: list[str], exercise_type: str = "fill_blank") -> str:
        """توليد تمارين من نوع معين."""
        if not words or not self.groq.is_ready:
            return self._fallback_exercises(words, exercise_type)

        word_list = ", ".join(words[:10])
        type_label = {
            "fill_blank": "fill-in-the-blank",
            "matching": "matching (word to definition)",
            "true_false": "true/false statements",
        }.get(exercise_type, "fill-in-the-blank")

        prompt = (
            f"Create 5 {type_label} exercises using these vocabulary words: {word_list}\n"
            "Number each exercise. Then provide an answer key at the end.\n"
            "Format:\n"
            "EXERCISES:\n1. ...\n2. ...\n\nANSWER KEY:\n1. ...\n2. ..."
        )
        try:
            return self.groq._call(prompt, timeout=15)
        except Exception as e:
            logger.error(f"Exercises generation: {e}")
            return self._fallback_exercises(words, exercise_type)

    def _fallback_story(self, words: list[str]) -> str:
        if not words:
            return "لا توجد كلمات كافية لإنشاء قصة."
        sample = ", ".join(words[:4])
        return f"لم يتم الاتصال بـ Groq AI.\nحاول استخدام الكلمات التالية في جملة:\n{sample}"

    def _fallback_dialogue(self, words: list[str]) -> str:
        if not words:
            return "لا توجد كلمات كافية."
        return (
            "A: Hello! How are you doing today?\n"
            "B: I'm doing well, thank you for asking!\n\n"
            "(تحتاج إلى Groq API لتوليد حوار باستخدام كلماتك)"
        )

    def _fallback_exercises(self, words: list[str], exercise_type: str) -> str:
        if not words:
            return "لا توجد كلمات كافية."
        lines = ["(تحتاج إلى Groq API لتوليد تمارين حقيقية)\n"]
        for i, w in enumerate(words[:5], 1):
            lines.append(f"{i}. Use the word '{w}' in a sentence: ___________")
        return "\n".join(lines)
