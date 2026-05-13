# services/youtube.py
"""
YouTubeSummarizer مستقل لتحليل محاضرات YouTube.
لا يعتمد على tkinter، يستخدم Database و GroqClient.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    HAS_YT = True
except ImportError:
    HAS_YT = False
    logger.warning("youtube-transcript-api not installed")


class YouTubeSummarizer:
    """يجلب transcript من YouTube، يلخصه، ويقترح كلمات للحفظ."""

    def __init__(self, db, groq: Any, pdf_manager: Any) -> None:
        self.db = db
        self.groq = groq
        self.pdf = pdf_manager

    @staticmethod
    def extract_video_id(url: str) -> str:
        url = url.strip()
        match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
        if match:
            return match.group(1)
        if re.match(r"^[A-Za-z0-9_-]{11}$", url):
            return url
        return ""

    def fetch_transcript(self, video_id: str) -> tuple[str, str]:
        if not HAS_YT:
            return "", "youtube-transcript-api غير مثبّتة"
        try:
            try:
                api = YouTubeTranscriptApi()
                entries = api.fetch(video_id, languages=["en"])
            except (TypeError, AttributeError):
                entries = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
            if not entries:
                return "", "لا يوجد transcript"
            texts = [e.get("text", "") if isinstance(e, dict) else getattr(e, "text", str(e)) for e in entries]
            transcript = re.sub(r"\s+", " ", " ".join(filter(None, texts))).strip()
            return transcript, ""
        except Exception as e:
            msg = str(e)
            if "Subtitles are disabled" in msg or "TranscriptsDisabled" in msg:
                return "", "الترجمة النصية معطلة لهذا الفيديو"
            if "NoTranscriptFound" in msg:
                return "", "لا يوجد transcript إنجليزي"
            return "", f"خطأ: {msg}"

    def summarize(self, transcript: str, title: str = "") -> dict:
        if not self.groq.is_ready:
            words = transcript.split()
            return {"key_points": [], "terms": [], "questions": [],
                    "hard_words": [], "summary": " ".join(words[:80]) + "..."}

        words = transcript.split()
        if len(words) > 6000:
            transcript = " ".join(words[:6000]) + " [...]"

        prompt = (
            f'Summarize this lecture transcript.\n'
            f'Title: "{title}"\n\nTRANSCRIPT:\n{transcript}\n\n'
            f'Return ONLY valid JSON, no markdown:\n'
            f'{{\n'
            f'  "key_points": ["نقطة 1 بالعربي", "نقطة 2", "..."],\n'
            f'  "terms": [{{"term":"English","definition":"Arabic"}}, ...],\n'
            f'  "questions": ["سؤال 1؟", "..."],\n'
            f'  "hard_words": ["word1","word2","...","word8"]\n'
            f'}}'
        )
        try:
            raw = self.groq._call(prompt, timeout=30)
            raw = re.sub(r"```(?:json)?", "", raw).strip("`").strip()
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error(f"YT summarize: {e}")
        return {"key_points": [], "terms": [], "questions": [], "hard_words": []}

    def build_pdf_text(self, url: str, title: str, data: dict, char_count: int) -> str:
        from datetime import datetime
        sep = "=" * 52
        lines = [sep, "    YOUTUBE LECTURE SUMMARY", sep,
                 f"Date:   {datetime.now().strftime('%Y-%m-%d  %H:%M')}",
                 f"URL:    {url}", f"Title:  {title or '—'}",
                 f"Length: ~{char_count:,} chars", sep, ""]
        if kp := data.get("key_points", []):
            lines += ["KEY POINTS", "-" * 30]
            for i, pt in enumerate(kp, 1): lines.append(f"  {i}. {pt}")
            lines.append("")
        if terms := data.get("terms", []):
            lines += ["IMPORTANT TERMS", "-" * 30]
            for t in terms:
                if isinstance(t, dict):
                    lines.append(f"  • {t.get('term','')}  —  {t.get('definition','')}")
            lines.append("")
        if qs := data.get("questions", []):
            lines += ["SUGGESTED QUESTIONS", "-" * 30]
            for q in qs: lines.append(f"  ? {q}")
            lines.append("")
        if hw := data.get("hard_words", []):
            lines += ["VOCABULARY SAVED", "-" * 30]
            lines.append("  " + "  |  ".join(hw))
            lines.append("")
        lines.append(sep)
        return "\n".join(lines)

    def save_hard_words(self, words: list[str], subject: str) -> int:
        from deep_translator import GoogleTranslator
        saved = 0
        for word in words:
            if self.db.word_exists(word):
                continue
            try:
                tr_val = GoogleTranslator(source="en", target="ar").translate(word) or word
                enriched = self.groq.enrich_word(word, tr_val)
                alts = [a for a in enriched.get("alt_translations", []) if a and a != tr_val]
                entry = {
                    "Word": word, "Translation": tr_val,
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
                    "SRS_Level": 0, "Next_Review": date.today().isoformat(),
                    "Total_Reviews": 0, "Correct_Reviews": 0,
                    "Subject": subject, "Added_Date": date.today().isoformat(),
                }
                if self.db.add_word(entry):
                    self.db.log_word_added()
                    saved += 1
            except Exception as e:
                logger.error(f"YT word save '{word}': {e}")
        return saved