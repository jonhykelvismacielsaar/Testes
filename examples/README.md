# Exemplos VoiceStudio Arena

## 1. TTS direto via agente Arena

```python
# No chat com o agente, peça:
# "Crie uma voz feminina brasileira acolhedora e fale: Olá, bem-vindo ao VoiceStudio Arena!"
# O agente fará:
# add_voice(text="voz feminina brasileira acolhedora...", language="pt-BR") -> voice_id
# generate_speech(file_path="ola.mp3", text="Olá, bem-vindo...", voice_id=voice_id)
```

## 2. Dublagem via API

```bash
curl -X POST http://localhost:3900/api/dub \
  -F source_lang=pt-BR -F target_lang=en-US \
  -F voice=en-US-JennyNeural \
  -F file=@video.mp4
```

## 3. Audiobook de PDF

```bash
curl -X POST http://localhost:3900/api/audiobook/pdf \
  -F file=@livro.pdf -F voice=pt-BR-FranciscaNeural -F title="Dom Casmurro"
```

## 4. Transcrição OpenAI-compat

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:3900/v1", api_key="sk-fake")
with open("audio.mp3","rb") as f:
    print(client.audio.transcriptions.create(model="whisper-1", file=f).text)
```

## 5. Python bridge

```python
import requests
r = requests.post("http://localhost:3900/api/generate", json={
  "text": "Olá mundo, este é um teste do VoiceStudio Arena com 646 idiomas.",
  "voice": "pt-BR-FranciscaNeural",
  "engine": "arena-tts"
})
print(r.json())
# Baixar áudio: requests.get(f"http://localhost:3900/api/audio/{r.json()['id']}").content
```
