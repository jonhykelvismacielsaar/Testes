from pathlib import Path
import uuid
import json
from datetime import datetime
from ..config import OUTPUTS_DIR
from .transcription import transcribe
from .generation import synthesize

# Tradução — tentar argos, senão mock
try:
    import argostranslate.translate
    HAS_ARGOS = True
except ImportError:
    HAS_ARGOS = False

def translate_text(text: str, source: str, target: str) -> str:
    if HAS_ARGOS:
        try:
            # argos usa códigos como 'en', 'pt'
            src = source.split("-")[0]
            tgt = target.split("-")[0]
            translated = argostranslate.translate.translate(text, src, tgt)
            if translated and translated.strip():
                return translated
        except Exception as e:
            print(f"[dub] argos falhou: {e}")
    # Fallback mock — prefixa idioma
    prefixes = {
        "en": "🇺🇸 ", "es": "🇪🇸 ", "fr": "🇫🇷 ", "ja": "🇯🇵 ", "zh": "🇨🇳 ", "pt": "🇧🇷 "
    }
    p = prefixes.get(target.split("-")[0], f"[{target}] ")
    return p + text

async def dub_pipeline(audio_path: Path, source_lang: str = "pt-BR", target_lang: str = "en-US", voice: str = "en-US-JennyNeural", engine: str = "arena-tts") -> dict:
    """
    Pipeline de dublagem espelhando VoiceStudio:
    1. Transcrever
    2. Traduzir
    3. Sintetizar com voz alvo
    """
    dub_id = uuid.uuid4().hex[:8]
    # 1. Transcrever
    transcription = await transcribe(audio_path, language=source_lang.split("-")[0])
    original_text = transcription.get("text", "")

    # 2. Traduzir
    translated = translate_text(original_text, source_lang, target_lang)

    # 3. TTS
    result = await synthesize(translated, voice, engine_id=engine)

    return {
        "id": dub_id,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "original_text": original_text,
        "translated_text": translated,
        "audio": result,
        "transcription": transcription,
        "created_at": datetime.utcnow().isoformat(),
    }

async def dub_video(video_path: Path, **kwargs) -> dict:
    """
    Para vídeo: extrai áudio, dubla, remuxa (simulado aqui)
    """
    # Extrair áudio com ffmpeg se disponível, senão usar video_path direto como áudio
    import shutil, subprocess, tempfile
    audio_path = video_path
    if shutil.which("ffmpeg"):
        try:
            tmp_audio = OUTPUTS_DIR / f"extract_{uuid.uuid4().hex[:6]}.wav"
            subprocess.run(["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(tmp_audio)], capture_output=True, timeout=30)
            if tmp_audio.exists():
                audio_path = tmp_audio
        except Exception as e:
            print(f"[dub_video] ffmpeg falhou: {e}")

    return await dub_pipeline(audio_path, **kwargs)
