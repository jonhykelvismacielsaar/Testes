import os
from pathlib import Path

# Diretórios
ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "data"
VOICES_DIR = DATA_DIR / "voices"
OUTPUTS_DIR = DATA_DIR / "outputs"
UPLOADS_DIR = DATA_DIR / "uploads"

for d in [VOICES_DIR, OUTPUTS_DIR, UPLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Configurações
PRODUCT_NAME = "VoiceStudio Arena"
VERSION = "0.1.0-arena"
DEFAULT_PORT = int(os.getenv("VOICESTUDIO_PORT", "3900"))
DEFAULT_HOST = os.getenv("VOICESTUDIO_HOST", "0.0.0.0")

# Engines disponíveis — espelha o catálogo do VoiceStudio
ENGINES = {
    "arena-tts": {
        "label": "Arena TTS (nativo — via modelo do Arena)",
        "role": "TTS",
        "langs": 646,
        "desc": "Usa o motor de voz nativo do Arena (add_voice/generate_speech). Qualidade premium, clonagem zero-shot."
    },
    "edge-tts": {
        "label": "Edge TTS (Microsoft — 140+ vozes, gratuito)",
        "role": "TTS",
        "langs": 140,
        "desc": "Vozes neurais da Microsoft, sem API key. Ideal para testes."
    },
    "gtts": {
        "label": "gTTS (Google — leve)",
        "role": "TTS",
        "langs": 40,
        "desc": "Fallback leve, funciona offline com cache."
    },
    "mock": {
        "label": "Mock (simulação)",
        "role": "TTS",
        "langs": 646,
        "desc": "Retorna áudio placeholder — útil para testar pipeline sem modelo."
    },
    "whisper": {
        "label": "Whisper (faster-whisper local)",
        "role": "ASR",
        "langs": 99,
        "desc": "Transcrição local via CTranslate2. Instale faster-whisper para ativar."
    },
    "mock-asr": {
        "label": "Mock ASR",
        "role": "ASR",
        "langs": 99,
        "desc": "Simulação — retorna texto de exemplo."
    }
}

# Vozes de demonstração (mapeadas para Edge-TTS e Arena)
DEMO_VOICES = [
    {"id": "pt-BR-FranciscaNeural", "name": "Francisca", "lang": "pt-BR", "gender": "feminine", "engine": "edge-tts", "sample": "Olá, eu sou a Francisca, uma voz brasileira calorosa."},
    {"id": "pt-BR-AntonioNeural", "name": "Antônio", "lang": "pt-BR", "gender": "masculine", "engine": "edge-tts", "sample": "Olá, eu sou o Antônio, pronto para narrar sua história."},
    {"id": "en-US-JennyNeural", "name": "Jenny", "lang": "en-US", "gender": "feminine", "engine": "edge-tts", "sample": "Hello, I'm Jenny, your friendly US narrator."},
    {"id": "en-US-GuyNeural", "name": "Guy", "lang": "en-US", "gender": "masculine", "engine": "edge-tts", "sample": "Hey there, I'm Guy with a natural American voice."},
    {"id": "es-ES-ElviraNeural", "name": "Elvira", "lang": "es-ES", "gender": "feminine", "engine": "edge-tts", "sample": "Hola, soy Elvira, tu voz española."},
    {"id": "ja-JP-NanamiNeural", "name": "Nanami", "lang": "ja-JP", "gender": "feminine", "engine": "edge-tts", "sample": "こんにちは、私はナナミです。"},
    {"id": "fr-FR-DeniseNeural", "name": "Denise", "lang": "fr-FR", "gender": "feminine", "engine": "edge-tts", "sample": "Bonjour, je suis Denise."},
    {"id": "arena-clone-01", "name": "Voz Clonada (Arena)", "lang": "pt-BR", "gender": "feminine", "engine": "arena-tts", "sample": "Voz clonada via Arena — idêntica à amostra enviada."},
]

# Idiomas suportados (resumo do VoiceStudio 646 → mapeados aqui para UI)
LANGUAGES = [
    ("pt-BR", "Português (Brasil)"), ("pt-PT", "Português (Portugal)"),
    ("en-US", "English (US)"), ("en-GB", "English (UK)"),
    ("es-ES", "Español"), ("es-MX", "Español (México)"),
    ("fr-FR", "Français"), ("de-DE", "Deutsch"), ("it-IT", "Italiano"),
    ("ja-JP", "日本語"), ("zh-CN", "中文"), ("ko-KR", "한국어"),
    ("ru-RU", "Русский"), ("ar-SA", "العربية"), ("hi-IN", "हिन्दी"),
]

VOICE_DESIGN_PRESETS = [
    {"id": "narrator-warm", "label": "Narrador acolhedor", "prompt": "voz masculina grave e acolhedora, ritmo calmo, ideal para audiobook"},
    {"id": "podcaster-energetic", "label": "Podcaster energética", "prompt": "voz feminina jovem, energética, conversacional, brasileira"},
    {"id": "villain-gravelly", "label": "Vilão rouco", "prompt": "voz masculina rouca, grave, ameaçadora, com sussurro"},
    {"id": "support-calm", "label": "Atendente calmo", "prompt": "voz neutra, calma, profissional, ritmo moderado"},
    {"id": "news-anchor", "label": "Âncora de jornal", "prompt": "voz clara, autoritativa, ritmo jornalístico americano"},
    {"id": "bedtime-soft", "label": "Contadora de histórias", "prompt": "voz feminina suave, sussurrada, ideal para histórias de dormir"},
]
