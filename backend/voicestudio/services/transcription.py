from pathlib import Path
from typing import Optional
from ..engines.mock_engine import MockASREngine

# Tentar carregar faster-whisper se disponível
try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False
    WhisperModel = None

_model_cache = {}

def get_whisper_model(model_size="base"):
    if not HAS_FASTER_WHISPER:
        return None
    if model_size not in _model_cache:
        # CPU, int8 para rodar leve
        _model_cache[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model_cache[model_size]

async def transcribe(audio_path: Path, language: Optional[str] = None, model: str = "base") -> dict:
    """
    Transcreve áudio. Usa faster-whisper se instalado, senão mock.
    Retorno compatível com VoiceStudio /v1/audio/transcriptions
    """
    if HAS_FASTER_WHISPER:
        try:
            m = get_whisper_model(model)
            segments, info = m.transcribe(str(audio_path), language=language, beam_size=5, word_timestamps=True)
            segs = []
            full_text = ""
            for s in segments:
                segs.append({"start": s.start, "end": s.end, "text": s.text})
                full_text += s.text
            return {
                "text": full_text.strip(),
                "language": info.language,
                "duration": info.duration,
                "segments": segs,
                "engine": "faster-whisper",
                "model": model
            }
        except Exception as e:
            print(f"[transcription] faster-whisper falhou: {e}, usando mock")

    # Fallback mock
    mock = MockASREngine()
    return await mock.transcribe(audio_path, language)

async def transcribe_with_diarization(audio_path: Path, language: Optional[str] = None) -> dict:
    """Transcrição + diarização (simulada se sem modelo)"""
    base = await transcribe(audio_path, language)
    # Adicionar speakers mock
    base["diarization"] = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": base.get("duration", 5)/2, "text": "Primeiro falante..."},
        {"speaker": "SPEAKER_01", "start": base.get("duration", 5)/2, "end": base.get("duration", 5), "text": "Segundo falante..."},
    ]
    return base
