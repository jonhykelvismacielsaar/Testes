from pathlib import Path
from typing import Optional
from .base import ASREngine
import json
import wave
import struct
import math

class MockASREngine(ASREngine):
    id = "mock-asr"
    label = "Mock ASR"

    async def transcribe(self, audio_path: Path, language: Optional[str] = None) -> dict:
        # Mock — retorna transcrição placeholder mas com estrutura idêntica ao WhisperX
        return {
            "text": "Olá, esta é uma transcrição simulada. Instale faster-whisper para transcrição real local.",
            "language": language or "pt",
            "segments": [
                {"start": 0.0, "end": 2.1, "text": "Olá, esta é uma transcrição simulada."},
                {"start": 2.1, "end": 4.5, "text": "Instale faster-whisper para transcrição real local."}
            ],
            "engine": self.id
        }

class MockDubEngine:
    """Simula dublagem: texto -> tradução mock -> TTS"""
    @staticmethod
    def translate_mock(text: str, target_lang: str) -> str:
        translations = {
            "en": f"[EN] {text}",
            "es": f"[ES] Traducción simulada: {text}",
            "fr": f"[FR] Traduction simulée: {text}",
            "ja": f"[JA] 翻訳: {text}",
            "zh": f"[ZH] 翻译: {text}",
        }
        return translations.get(target_lang[:2], f"[{target_lang}] {text}")
