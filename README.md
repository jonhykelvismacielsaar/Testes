# VoiceStudio Arena — Clone de Funcionalidades para Arena.ai

> **Clone funcional do [VoiceStudio](https://github.com/debpalash/VoiceStudio) — estúdio de voz open-source com clonagem, design de voz, dublagem, ditado, transcrição e audiobooks em 646 idiomas.**

Este repositório replica as principais funcionalidades do VoiceStudio para uso **dentro do Arena.ai** e também como app standalone.

![License](https://img.shields.io/badge/license-AGPL--3.0-blue) ![Python](https://img.shields.io/badge/python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)

---

## ✨ Funcionalidades clonadas

| Feature | VoiceStudio original | Este clone |
|---|---|---|
| **Voice Cloning** | OmniVoice zero-shot (2.4GB) | Arena TTS nativo (`add_voice` + `generate_speech`) + Edge-TTS fallback |
| **Voice Design** | Prompt → voz (OmniVoice) | `POST /api/voices/design` — prompt → perfil reutilizável |
| **Video Dubbing** | Transcribe → Translate → TTS + lip-sync | `POST /api/dub` com tradução + pipeline igual |
| **Transcription** | WhisperX / faster-whisper / MLX | `POST /api/transcribe` + OpenAI `/v1/audio/transcriptions` + diarização |
| **Audiobook** | Batch + longform | `POST /api/audiobook` (texto/PDF → capítulos → audios) |
| **Dictation (live)** | `ws://:3900/v1/audio/transcriptions/stream` | WebSocket idêntico com parciais |
| **OpenAI API** | `POST /v1/audio/speech` | Compatível — drop-in replacement |
| **MCP / Agents** | Cloud sync + MCP | `/api/tools` + `arena_bridge.py` |
| **Frontend** | Electron + React 19 | `frontend/index.html` — 7 workspaces dark modernos |

### Compatibilidade de API

O backend implementa os mesmos paths do VoiceStudio, para que clients existentes funcionem sem mudança:

- `GET /.well-known/voicestudio-speech`
- `POST /api/generate`, `GET /api/audio/{id}`, `GET /api/generations`
- `GET|POST /api/voices`, `/api/voices/clone`, `/api/voices/design`
- `POST /api/transcribe`, `/api/dub`, `/api/audiobook`
- `POST /v1/audio/speech`, `/v1/audio/transcriptions`, `/v1/audio/translations`
- `GET /v1/models`, `GET /v1/audio/voices`
- `WS /v1/audio/transcriptions/stream` e `WS /ws/transcribe`

---

## 🚀 Início rápido

### Opção 1 — Usando direto no Arena (sem instalar nada)

Você já pode pedir no chat:

> "Crie uma voz feminina brasileira acolhedora e narre: Olá, bem-vindo ao VoiceStudio Arena!"

O agente usa nativamente `add_voice` e `generate_speech` — mesma qualidade do VoiceStudio, zero config.

Veja [`docs/ARENA.md`](docs/ARENA.md) para o guia completo de integração.

#### 🎥 Só consigo anexar vídeo (não áudio)? Sem problema

O clone aceita **vídeo** como amostra de voz. Ele extrai a faixa de áudio,
remove ruído de fundo e normaliza o volume (ffmpeg embutido via `imageio-ffmpeg`):

```bash
# direto no chat: anexe um vídeo falando e peça "clona essa voz"
# ou via linha de comando:
python3 tools/preparar_voz.py meu-video.mp4 -o data/uploads/minha_voz.wav -i 3 -d 20
#   -i 3   → começa no segundo 3
#   -d 20  → pega 20 segundos
#   --ultimo → usa automaticamente o vídeo mais recente do workspace

# conferir qualidade antes de clonar
curl -X POST http://localhost:3900/api/voices/extract -F file=@meu-video.mp4 -F duration=20

# clonar direto do vídeo (extração automática)
curl -X POST http://localhost:3900/api/voices/clone \
  -F name="Minha Voz" -F language=pt-BR -F gender=feminine \
  -F duration=20 -F sample=@meu-video.mp4
```

A resposta inclui `quality` com duração, pico, RMS e avisos (amostra curta,
ruidosa, baixa, saturada). Dica: grave 15–30s falando de frente, sem música.

### 🌐 A interface principal: Estúdio de Voz

Abra a raiz do servidor (`/`) — é uma página única, sem dependências externas:

1. **Sua voz** — grave pelo microfone **ou** escolha um áudio/vídeo direto do
   aparelho (não precisa anexar nada no chat).
2. **O que falar** — escreva o texto.
3. **Ouvir falando** — o áudio toca na hora com as vozes neurais do dispositivo;
   “Gerar arquivo de áudio” tenta os motores do servidor e avisa se estiver offline.

A versão completa com as 7 abas (clone do app original) fica em `/classic`.

### Opção 2 — Backend + Frontend local

```bash
# 1. Instalar dependências
pip install -r backend/requirements.txt

# 2. Subir API (http://localhost:3900)
python backend/main.py
# ou
uvicorn backend.main:app --host 0.0.0.0 --port 3900 --reload

# 3. Abrir frontend
# http://localhost:3900/  (servido pelo backend)
# ou abrir direto: frontend/index.html
# Docs: http://localhost:3900/docs
```

### Exemplos curl

```bash
# TTS
curl -X POST http://localhost:3900/api/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Olá mundo, este é o VoiceStudio Arena!","voice":"pt-BR-FranciscaNeural"}'

# Clonar voz
curl -X POST http://localhost:3900/api/voices/clone \
  -F name="Minha Voz" -F language=pt-BR -F gender=feminine -F sample=@voz.wav

# Dublar texto
curl -X POST http://localhost:3900/api/dub \
  -F source_lang=pt-BR -F target_lang=en-US -F voice=en-US-JennyNeural -F text="Olá, tudo bem?"

# Audiobook PDF
curl -X POST http://localhost:3900/api/audiobook/pdf \
  -F file=@livro.pdf -F voice=pt-BR-FranciscaNeural -F title="Meu Livro"

# Transcrever (OpenAI compat)
curl -X POST http://localhost:3900/v1/audio/transcriptions \
  -F file=@audio.mp3 -F model=whisper-1
```

---

## 🧩 Integração Arena → VoiceStudio

Arquivo-chave: `backend/voicestudio/arena_bridge.py`

```python
from backend.voicestudio.arena_bridge import ArenaVoiceBridge

bridge = ArenaVoiceBridge(add_voice_fn=add_voice, generate_speech_fn=generate_speech)
# O bridge traduz chamadas VoiceStudio → tools nativas do Arena
```

O frontend e o backend já vêm configurados para usar o **engine `arena-tts`** como padrão — quando rodando no Arena, o áudio é gerado pelas tools nativas (qualidade premium). Fora do Arena, cai automaticamente para `edge-tts` (Microsoft Neural, 140+ vozes, gratuito).

---

## 📁 Estrutura

```
.
├── backend/
│   ├── main.py                    # FastAPI — todos os endpoints VoiceStudio
│   ├── requirements.txt
│   └── voicestudio/
│       ├── config.py              # catálogo de engines/idiomas/vozes
│       ├── arena_bridge.py        # ponte Arena (add_voice/generate_speech)
│       ├── engines/
│       │   ├── base.py
│       │   ├── arena_tts.py       # Arena TTS + Edge-TTS + gTTS fallback
│       │   └── mock_engine.py
│       └── services/
│           ├── voices.py          # clonagem & design
│           ├── generation.py      # TTS + histórico
│           ├── transcription.py   # Whisper / mock
│           ├── dubbing.py         # pipeline dub
│           └── audiobook.py       # capítulos + PDF
├── frontend/
│   ├── index.html                 # UI completa (7 workspaces)
│   └── app.js
├── docs/
│   └── ARENA.md                   # guia de uso no Arena
├── examples/
│   └── README.md
└── data/                          # voices, outputs, uploads (gitignored)
```

---

## 🔧 Engines

| ID | Label | Uso |
|---|---|---|
| `arena-tts` | Arena TTS (nativo) | **Padrão no Arena** — qualidade máxima |
| `edge-tts` | Microsoft Edge TTS | Fallback local — 140 vozes neurais gratuitas |
| `gtts` | Google gTTS | Fallback leve offline |
| `mock` | Mock | Teste de pipeline sem rede |
| `whisper` / `mock-asr` | Transcrição | faster-whisper se instalado, senão mock |

Para ativar transcrição real:

```bash
pip install faster-whisper
# e opcional para tradução offline:
pip install argostranslate
```

---

## 📜 Licença e créditos

- Original: **[debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio)** — AGPL-3.0
- Este clone mantém **AGPL-3.0** — uso comercial exige cumprir AGPL ou obter licença comercial do upstream.
- Vozes Edge-TTS são da Microsoft; gTTS do Google; modelos OmniVoice são Apache-2.0.

> Clone voices only with permission. Use responsável. O aviso de licença do VoiceStudio original aplica-se integralmente.

---

## 🙏 Agradecimentos

Obrigado ao [@debpalash](https://github.com/debpalash) e à comunidade VoiceStudio pelo trabalho excepcional. Este clone existe para levar essas funcionalidades a usuários do Arena.ai que não podem rodar o Electron localmente.

---

**Feito com ♥ para o Arena.ai** • [Abrir no Arena](https://arena.ai) • [VoiceStudio original](https://voicestudio.sh)
