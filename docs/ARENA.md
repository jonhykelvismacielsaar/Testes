# VoiceStudio Arena — Como usar dentro do Arena.ai

Este documento explica como **você (o agente Arena)** utiliza as funcionalidades clonadas do VoiceStudio.

## 1. Arquitetura

O VoiceStudio original (https://github.com/debpalash/VoiceStudio) é um app Electron + FastAPI com:
- TTS OmniVoice (2.4GB), WhisperX, diarização, dubbing pipeline, audiobook, ditado ao vivo via WebSocket e API OpenAI-compatível.

O clone **VoiceStudio Arena** replica tudo isso em:
- `backend/main.py` — FastAPI com os mesmos endpoints
- `frontend/index.html` — UI dark moderna equivalente ao Electron
- `backend/voicestudio/engines/arena_tts.py` — ponte para as tools nativas do Arena

```
Arena Agent (você)
  ├── add_voice  ──────┐
  ├── generate_speech ─┤──→ áudio real (nativo Arena)
  └── HTTP localhost:3900 ──→ transcrição, dublagem, audiobook, etc.
```

## 2. Uso direto (sem HTTP) — recomendado

Quando o usuário pede voz, você já pode gerar **sem** subir o backend:

```python
# 1. Registrar voz (voice design / clonagem por descrição)
voice_id = add_voice(
  text="Uma voz feminina brasileira calorosa, perfeita para audiobook, com ritmo calmo e envolvente.",
  language="pt-BR",
  voice_identity={"gender": "feminine", "use_case": "narration"}
)

# 2. Sintetizar
generate_speech(
  file_path="saida.mp3",
  text="Olá! Este é o VoiceStudio Arena falando. Posso clonar qualquer voz com apenas alguns segundos de áudio.",
  voice_id=voice_id
)
```

### Quando usar cada tool

| Pedido do usuário | O que fazer |
|---|---|
| "clone minha voz" + áudio | `add_voice` com transcrição da amostra + `generate_speech` |
| "crie uma voz de narradora" | `add_voice` com prompt descritivo |
| "fale esse texto" | `generate_speech` direto |
| "duble esse vídeo" | Chamar backend `/api/dub` + `generate_speech` para o resultado |
| "transcreva" | Chamar backend `/api/transcribe` (usa faster-whisper local) |
| "crie audiobook" | Chamar backend `/api/audiobook` |

## 3. Uso via backend (features completas)

Para dubbing, transcrição e audiobook, suba o backend:

```bash
pip install -r backend/requirements.txt
python backend/main.py
# → http://localhost:3900
# → docs em http://localhost:3900/docs
# → frontend em http://localhost:3900/ ou /frontend/
```

### Exemplos curl (todos compatíveis com VoiceStudio original)

```bash
# Gerar
curl -X POST http://localhost:3900/api/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"Olá mundo","voice":"pt-BR-FranciscaNeural","engine":"arena-tts"}'

# Clonar voz (multipart)
curl -X POST http://localhost:3900/api/voices/clone \
  -F name="Minha Voz" -F language=pt-BR -F gender=feminine -F sample=@amostra.wav

# Voice design
curl -X POST http://localhost:3900/api/voices/design \
  -H "Content-Type: application/json" \
  -d '{"name":"Narradora","prompt":"voz feminina calorosa brasileira","language":"pt-BR"}'

# Transcrever
curl -X POST http://localhost:3900/api/transcribe -F file=@audio.mp3 -F language=pt

# Dublar (texto)
curl -X POST http://localhost:3900/api/dub \
  -F source_lang=pt-BR -F target_lang=en-US -F voice=en-US-JennyNeural -F text="Olá, como vai?"

# Audiobook
curl -X POST http://localhost:3900/api/audiobook \
  -H "Content-Type: application/json" \
  -d '{"title":"Meu Livro","text":"Era uma vez...","voice":"pt-BR-FranciscaNeural"}'

# OpenAI compat
curl http://localhost:3900/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"tts-1","input":"Hello","voice":"alloy"}'
```

### WebSocket ditado ao vivo

Igual ao VoiceStudio `speech-platform.md`:

```js
const ws = new WebSocket("ws://localhost:3900/v1/audio/transcriptions/stream");
ws.onopen = () => {
  // enviar PCM ou WebM/Opus como bytes
  ws.send(mediaRecorderChunk);
};
ws.onmessage = e => {
  const msg = JSON.parse(e.data);
  if(msg.type==="partial") showPartial(msg.text);
  if(msg.type==="final") showFinal(msg.text);
};
// finalizar sem fechar: ws.send(JSON.stringify({type:"input_audio.end"}));
```

## 4. Bridge Python para o agente

```python
from backend.voicestudio.arena_bridge import ArenaVoiceBridge

bridge = ArenaVoiceBridge(add_voice_fn=add_voice, generate_speech_fn=generate_speech)
print(bridge.instructions_for_agent())  # prompt completo
caps = bridge.describe_capabilities()
```

## 5. Frontend

Abra `frontend/index.html` direto ou via backend (`http://localhost:3900/`).
Tem 7 workspaces idênticos ao Electron original:
- Clonar & Gerar, Design de Voz, Dublagem, Transcrição, Audiobook, Ditado, Modelos

## 6. Próximos passos para paridade total

- Trocar `edge-tts` por `OmniVoice` local (2.4GB) quando tiver GPU
- Adicionar `faster-whisper` para transcrição real: `pip install faster-whisper`
- Adicionar Argos Translate para tradução offline
- Conectar `backend.speech_client` Python para ditado nativo (igual VoiceStudio)

Licença: AGPL-3.0 — igual ao original. Uso comercial exige cumprir AGPL ou licença comercial separada.


## 7. Clonar voz quando o chat só aceita vídeo 🎥

O Arena aceita anexos de imagem e vídeo; se o áudio não puder ser enviado,
**grave um vídeo de 15–30s falando** (pode ser a câmera tampada — o que importa
é o microfone) e peça no chat:

> "Extraia a voz desse vídeo e clone. Depois fale: *seu texto*"

O agente executa:

```bash
# 1. extrai + limpa + normaliza a voz
python3 tools/preparar_voz.py meu-video.mp4 -o data/uploads/minha_voz.wav -d 20

# 2. registra a voz no Arena
add_voice(text="<transcrição da fala>", language="pt-BR",
          voice_identity={"gender": "feminine", "use_case": "narration"})

# 3. fala qualquer texto com a voz clonada
generate_speech(file_path="saida.mp3", text="...", voice_id="voice-XX")
```

### O que a limpeza faz

| Etapa | Filtro | Efeito |
|---|---|---|
| 1 | `highpass=80` | remove ruído grave (ventilador, ar-condicionado) |
| 2 | `lowpass=10000` | remove chiado agudo |
| 3 | `afftdn` | redução de ruído por FFT |
| 4 | `loudnorm` | volume padrão de podcast (-16 LUFS) |
| 5 | `aresample=24000` + mono | formato ideal para clonagem |

### Endpoints novos

```bash
# preparar amostra (não cria voz) — devolve métricas de qualidade
POST /api/voices/extract      (multipart: file, start?, duration?, denoise?)
GET  /api/uploads/{arquivo}   # baixar o WAV processado

# clonar aceitando vídeo
POST /api/voices/clone        (multipart: name, language, gender, sample,
                               start?, duration?, denoise?)
# resposta inclui "quality": {duration, peak_db, rms_db, warnings, ok}
```

### Qualidade da amostra

O retorno traz avisos automáticos quando:
- duração < 3s (ruim), < 8s (curta) — ideal 15–30s
- pico ≥ 0 dBFS (saturação/clipping)
- RMS < -45 dB (volume baixo)
- duração > 3min (desnecessário)

### Sem ffmpeg do sistema?

```bash
pip install imageio-ffmpeg
```

O módulo `backend/voicestudio/utils/audio.py` detecta `ffmpeg` no PATH e, se
não houver, usa o binário embutido do `imageio-ffmpeg` automaticamente.
