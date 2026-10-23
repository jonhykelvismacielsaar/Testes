import uuid
import json
import wave
from pathlib import Path
from datetime import datetime
from ..config import OUTPUTS_DIR
from ..engines.arena_tts import ArenaTTSEngine, EdgeTTSEngine, MockTTSEngine

ENGINES = {
    "arena-tts": ArenaTTSEngine(),
    "edge-tts": EdgeTTSEngine(),
    "mock": MockTTSEngine(),
}

HISTORY_FILE = OUTPUTS_DIR / "history.json"

def _load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except:
            return []
    return []

def _save_history(h):
    HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")

async def synthesize(text: str, voice: str, engine_id: str = "arena-tts", rate: str = "+0%", pitch: str = "+0Hz", **kw) -> dict:
    if not text or not text.strip():
        raise ValueError("Texto vazio")
    if len(text) > 8000:
        raise ValueError("Texto muito longo (máx 8000 caracteres por geração)")

    engine = ENGINES.get(engine_id, ENGINES["arena-tts"])
    audio_id = uuid.uuid4().hex[:8]
    output_path = OUTPUTS_DIR / f"{audio_id}.wav"
    # Também manter mp3 para compatibilidade
    # Engines salvam direto

    await engine.synthesize(text, voice, output_path, rate=rate, pitch=pitch)

    # Se engine salvou mp3 em vez de wav, garantir wav
    if not output_path.exists():
        mp3 = output_path.with_suffix(".mp3")
        if mp3.exists():
            # criar wav placeholder para consistência
            output_path = mp3
        else:
            raise RuntimeError("Falha na síntese — nenhum arquivo gerado")

    duration = estimate_duration(text)
    entry = {
        "id": audio_id,
        "text": text,
        "voice": voice,
        "engine": engine_id,
        "file": str(output_path.name),
        "path": str(output_path),
        "duration": duration,
        "created_at": datetime.utcnow().isoformat(),
        "chars": len(text)
    }
    hist = _load_history()
    hist.insert(0, entry)
    hist = hist[:100]  # manter 100 últimas
    _save_history(hist)
    return entry

def estimate_duration(text: str) -> float:
    # ~14 chars/sec média
    return round(max(1.0, len(text) / 14), 2)

def list_generations():
    return _load_history()

def get_generation(audio_id: str):
    for e in _load_history():
        if e["id"] == audio_id:
            return e
    return None

def delete_generation(audio_id: str):
    hist = _load_history()
    new = [h for h in hist if h["id"] != audio_id]
    if len(new) == len(hist):
        return False
    # remover arquivo
    for h in hist:
        if h["id"] == audio_id:
            try:
                Path(h["path"]).unlink(missing_ok=True)
                Path(h["path"]).with_suffix(".mp3").unlink(missing_ok=True)
            except:
                pass
    _save_history(new)
    return True
