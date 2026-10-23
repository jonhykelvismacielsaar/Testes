import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from ..config import VOICES_DIR, DEMO_VOICES

VOICES_DB = VOICES_DIR / "voices.json"

def _load_voices():
    if VOICES_DB.exists():
        try:
            return json.loads(VOICES_DB.read_text(encoding="utf-8"))
        except:
            pass
    # Seed com demos
    return list(DEMO_VOICES)

def _save_voices(voices):
    VOICES_DB.write_text(json.dumps(voices, ensure_ascii=False, indent=2), encoding="utf-8")

def list_voices():
    return _load_voices()

def get_voice(voice_id: str):
    for v in _load_voices():
        if v["id"] == voice_id:
            return v
    return None

def create_cloned_voice(name: str, language: str, gender: str, sample_path: Path | None, engine: str = "arena-tts"):
    voices = _load_voices()
    vid = f"clone-{uuid.uuid4().hex[:8]}"
    voice = {
        "id": vid,
        "name": name,
        "lang": language,
        "gender": gender,
        "engine": engine,
        "sample": f"Voz clonada: {name}",
        "cloned": True,
        "created_at": datetime.utcnow().isoformat(),
        "sample_path": str(sample_path) if sample_path else None
    }
    voices.append(voice)
    _save_voices(voices)
    return voice

def create_designed_voice(name: str, prompt: str, language: str = "pt-BR", gender: str = "feminine"):
    voices = _load_voices()
    vid = f"design-{uuid.uuid4().hex[:8]}"
    # Mapeia prompt para engine — no VoiceStudio real usaria OmniVoice voice_design
    # Aqui simulamos escolhendo Edge voice mais próxima
    edge_map = {
        "feminine": "pt-BR-FranciscaNeural",
        "masculine": "pt-BR-AntonioNeural",
    }
    base = edge_map.get(gender, "pt-BR-FranciscaNeural")
    voice = {
        "id": vid,
        "name": name,
        "lang": language,
        "gender": gender,
        "engine": "arena-tts",
        "base_voice": base,
        "prompt": prompt,
        "sample": f"Voz desenhada: {prompt[:80]}",
        "designed": True,
        "created_at": datetime.utcnow().isoformat(),
    }
    voices.append(voice)
    _save_voices(voices)
    return voice

def delete_voice(voice_id: str):
    voices = _load_voices()
    # Não deletar demos originais
    demo_ids = {v["id"] for v in DEMO_VOICES}
    if voice_id in demo_ids:
        return False
    new = [v for v in voices if v["id"] != voice_id]
    if len(new) == len(voices):
        return False
    _save_voices(new)
    return True
