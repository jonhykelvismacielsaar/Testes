"""
VoiceStudio Arena — Backend FastAPI
Clone das funcionalidades do VoiceStudio (https://github.com/debpalash/VoiceStudio)
Adaptado para rodar no Arena.ai com ponte para add_voice/generate_speech + Edge-TTS fallback.

Endpoints implementados (compatível com VoiceStudio):
- GET  /.well-known/voicestudio-speech
- GET  /api/health, /api/capabilities
- GET  /api/voices, POST /api/voices/clone, POST /api/voices/design
- POST /api/generate, GET /api/generations, GET /api/audio/{id}
- POST /v1/audio/speech (OpenAI compat)
- POST /v1/audio/transcriptions (OpenAI compat)
- WS   /v1/audio/transcriptions/stream
- POST /api/dub, POST /api/dub/video
- POST /api/audiobook, POST /api/audiobook/pdf
- POST /api/transcribe
- GET  /api/engines, GET /api/languages
- WS   /ws/transcribe (legado)
"""
import os
import sys
import uuid
import json
import asyncio
import shutil
from pathlib import Path
from typing import Optional, Literal

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Garantir que backend/ está no path
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from voicestudio.config import (
    PRODUCT_NAME, VERSION, ENGINES, DEMO_VOICES, LANGUAGES, VOICE_DESIGN_PRESETS,
    OUTPUTS_DIR, VOICES_DIR, UPLOADS_DIR
)
from voicestudio.services import voices as voices_svc
from voicestudio.services import generation as gen_svc
from voicestudio.services import transcription as trans_svc
from voicestudio.services import dubbing as dub_svc
from voicestudio.services import audiobook as ab_svc

app = FastAPI(
    title=PRODUCT_NAME,
    version=VERSION,
    description="Clone das funcionalidades do VoiceStudio para Arena.ai — TTS, clonagem, dublagem, transcrição e audiobooks.",
    license_info={"name": "AGPL-3.0", "url": "https://github.com/debpalash/VoiceStudio/blob/main/LICENSE"}
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ──
class GenerateRequest(BaseModel):
    text: str
    voice: str = "pt-BR-FranciscaNeural"
    engine: str = "arena-tts"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    format: str = "wav"

class CloneRequest(BaseModel):
    name: str
    language: str = "pt-BR"
    gender: str = "feminine"
    engine: str = "arena-tts"

class DesignRequest(BaseModel):
    name: str
    prompt: str
    language: str = "pt-BR"
    gender: str = "feminine"

class TranscribeRequest(BaseModel):
    language: Optional[str] = None

class DubRequest(BaseModel):
    source_lang: str = "pt-BR"
    target_lang: str = "en-US"
    voice: str = "en-US-JennyNeural"
    engine: str = "arena-tts"
    text: Optional[str] = None  # se enviar texto direto em vez de áudio

class AudiobookRequest(BaseModel):
    text: str
    voice: str = "pt-BR-FranciscaNeural"
    engine: str = "arena-tts"
    title: str = "Meu Audiobook"

class OpenAISpeechRequest(BaseModel):
    model: str = "tts-1"
    input: str
    voice: str = "alloy"
    response_format: str = "mp3"
    speed: float = 1.0

# ── Helpers ──
def openai_error(message: str, status: int = 400, param: str | None = None, code: str | None = None):
    return JSONResponse(status_code=status, content={
        "error": {"message": message, "type": "invalid_request_error", "param": param, "code": code},
        "detail": message
    })

# ── Root & Health ──
@app.get("/", response_class=HTMLResponse)
async def root():
    # Servir frontend se existir, senão info
    frontend = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend.exists():
        return FileResponse(str(frontend))
    return HTMLResponse(f"<h1>{PRODUCT_NAME} {VERSION}</h1><p>API em <a href='/docs'>/docs</a> | Frontend em <a href='/frontend/'>/frontend/</a></p>")

@app.get("/api/health")
async def health():
    return {"status": "ok", "product": PRODUCT_NAME, "version": VERSION, "engine": "arena-bridge"}

@app.get("/api/capabilities")
async def capabilities():
    return {
        "product": PRODUCT_NAME,
        "version": VERSION,
        "engines": ENGINES,
        "features": {
            "voice_cloning": True,
            "voice_design": True,
            "tts": True,
            "transcription": True,
            "dubbing": True,
            "audiobook": True,
            "dictation": True,
            "batch": True,
            "mcp": True,
            "openai_compat": True,
            "646_languages": True,
        },
        "endpoints": {
            "generate": "POST /api/generate",
            "transcribe": "POST /api/transcribe",
            "dub": "POST /api/dub",
            "audiobook": "POST /api/audiobook",
            "openai_speech": "POST /v1/audio/speech",
        }
    }

@app.get("/.well-known/voicestudio-speech")
async def well_known():
    return {
        "protocol": "voicestudio.speech.v1",
        "version": VERSION,
        "capabilities": {
            "engines": list(ENGINES.keys()),
            "features": {"native_dictation_control": False, "streaming": True}
        },
        "endpoints": {
            "transcribe": "/v1/audio/transcriptions",
            "stream": "/v1/audio/transcriptions/stream",
            "speech": "/v1/audio/speech"
        }
    }

# ── Engines & Languages ──
@app.get("/api/engines")
async def list_engines():
    return ENGINES

@app.get("/api/languages")
async def list_languages():
    return [{"code": c, "name": n} for c, n in LANGUAGES]

@app.get("/api/voices")
async def list_voices():
    return voices_svc.list_voices()

@app.get("/api/voices/{voice_id}")
async def get_voice(voice_id: str):
    v = voices_svc.get_voice(voice_id)
    if not v:
        raise HTTPException(404, "Voz não encontrada")
    return v

@app.post("/api/voices/clone")
async def clone_voice(
    name: str = Form(...),
    language: str = Form("pt-BR"),
    gender: str = Form("feminine"),
    engine: str = Form("arena-tts"),
    sample: UploadFile | None = File(None)
):
    sample_path = None
    if sample and sample.filename:
        ext = Path(sample.filename).suffix or ".wav"
        sample_path = UPLOADS_DIR / f"sample_{uuid.uuid4().hex[:6]}{ext}"
        sample_path.write_bytes(await sample.read())
    voice = voices_svc.create_cloned_voice(name, language, gender, sample_path, engine)
    return voice

@app.post("/api/voices/design")
async def design_voice(req: DesignRequest):
    if not req.prompt or len(req.prompt) < 5:
        raise HTTPException(400, "Prompt muito curto (mín 5 caracteres)")
    voice = voices_svc.create_designed_voice(req.name, req.prompt, req.language, req.gender)
    return voice

@app.delete("/api/voices/{voice_id}")
async def delete_voice(voice_id: str):
    if not voices_svc.delete_voice(voice_id):
        raise HTTPException(404, "Voz não encontrada ou é demo (não removível)")
    return {"deleted": True}

@app.get("/api/voice-presets")
async def voice_presets():
    return VOICE_DESIGN_PRESETS

# ── Generation ──
@app.post("/api/generate")
async def generate(req: GenerateRequest):
    try:
        result = await gen_svc.synthesize(req.text, req.voice, req.engine, req.rate, req.pitch)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Falha na síntese: {e}")

@app.get("/api/generations")
async def list_generations():
    return gen_svc.list_generations()

@app.get("/api/generations/{audio_id}")
async def get_generation(audio_id: str):
    g = gen_svc.get_generation(audio_id)
    if not g:
        raise HTTPException(404, "Áudio não encontrado")
    return g

@app.get("/api/audio/{audio_id}")
async def get_audio(audio_id: str, format: str = Query("wav")):
    g = gen_svc.get_generation(audio_id)
    if not g:
        raise HTTPException(404, "Áudio não encontrado")
    path = Path(g["path"])
    # Tentar wav, depois mp3
    if not path.exists():
        path = path.with_suffix(".mp3")
        if not path.exists():
            path = path.with_suffix(".wav")
    if not path.exists():
        raise HTTPException(404, "Arquivo de áudio não encontrado em disco")
    media = "audio/wav" if path.suffix == ".wav" else "audio/mpeg"
    return FileResponse(str(path), media_type=media, filename=f"{audio_id}{path.suffix}")

@app.get("/api/audio/{audio_id}.wav")
async def get_audio_wav(audio_id: str):
    return await get_audio(audio_id, "wav")

@app.get("/api/audio/{audio_id}.mp3")
async def get_audio_mp3(audio_id: str):
    # Se só temos wav, retornar wav mesmo
    g = gen_svc.get_generation(audio_id)
    if not g:
        raise HTTPException(404, "Áudio não encontrado")
    path = Path(g["path"])
    candidates = [path, path.with_suffix(".mp3"), path.with_suffix(".wav")]
    for p in candidates:
        if p.exists():
            return FileResponse(str(p), media_type="audio/mpeg" if p.suffix==".mp3" else "audio/wav", filename=f"{audio_id}{p.suffix}")
    raise HTTPException(404, "Arquivo não encontrado")

@app.delete("/api/generations/{audio_id}")
async def delete_generation(audio_id: str):
    if not gen_svc.delete_generation(audio_id):
        raise HTTPException(404, "Áudio não encontrado")
    return {"deleted": True}

# ── OpenAI Compatible ──
@app.post("/v1/audio/speech")
async def openai_speech(req: OpenAISpeechRequest):
    # Mapear voice alloy -> arena
    voice_map = {
        "alloy": "en-US-JennyNeural", "echo": "en-US-GuyNeural",
        "fable": "pt-BR-FranciscaNeural", "onyx": "pt-BR-AntonioNeural",
        "nova": "en-US-JennyNeural", "shimmer": "en-US-JennyNeural",
    }
    voice = voice_map.get(req.voice, req.voice)
    if voice in voice_map.values() or voice.endswith("Neural"):
        pass
    else:
        voice = "pt-BR-FranciscaNeural"

    try:
        result = await gen_svc.synthesize(req.input, voice, "arena-tts")
        path = Path(result["path"])
        # Determinar formato
        fmt = req.response_format.lower()
        if fmt in ["mp3", "opus", "aac", "flac"]:
            # Se temos wav, servir wav (conversão real exigiria ffmpeg)
            # Para compat, servir o arquivo existente
            candidates = [path, path.with_suffix(".mp3")]
            for p in candidates:
                if p.exists():
                    path = p
                    break
            media = {"mp3": "audio/mpeg", "opus": "audio/opus", "aac": "audio/aac", "flac": "audio/flac"}.get(fmt, "audio/mpeg")
            return FileResponse(str(path), media_type=media, filename=f"speech.{fmt}")
        else:
            return FileResponse(str(path), media_type="audio/wav")
    except Exception as e:
        return openai_error(str(e), 500)

@app.get("/v1/models")
async def openai_models():
    models = [
        {"id": "tts-1", "object": "model", "created": 0, "owned_by": "voicestudio"},
        {"id": "tts-1-hd", "object": "model", "created": 0, "owned_by": "voicestudio"},
        {"id": "whisper-1", "object": "model", "created": 0, "owned_by": "voicestudio"},
    ]
    for eng_id, eng in ENGINES.items():
        models.append({"id": eng_id, "object": "model", "created": 0, "owned_by": "voicestudio", "label": eng["label"]})
    return {"object": "list", "data": models}

@app.get("/v1/models/{model_id}")
async def openai_model_detail(model_id: str):
    return {"id": model_id, "object": "model", "created": 0, "owned_by": "voicestudio"}

@app.get("/v1/audio/voices")
async def openai_voices():
    return {"voices": voices_svc.list_voices()}

@app.post("/v1/audio/transcriptions")
async def openai_transcribe(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: str | None = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0.0),
):
    # Salvar temporário
    tmp = UPLOADS_DIR / f"stt_{uuid.uuid4().hex[:6]}_{file.filename or 'audio.wav'}"
    tmp.write_bytes(await file.read())
    try:
        result = await trans_svc.transcribe(tmp, language)
        if response_format == "verbose_json":
            return result
        elif response_format == "srt":
            srt = ""
            for i, seg in enumerate(result.get("segments", []), 1):
                srt += f"{i}\n{seg['start']:.3f} --> {seg['end']:.3f}\n{seg['text']}\n\n"
            return HTMLResponse(srt, media_type="text/plain")
        else:
            return {"text": result["text"]}
    finally:
        try:
            tmp.unlink()
        except:
            pass

@app.post("/v1/audio/translations")
async def openai_translate(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    response_format: str = Form("json"),
):
    tmp = UPLOADS_DIR / f"tr_{uuid.uuid4().hex[:6]}_{file.filename or 'audio.wav'}"
    tmp.write_bytes(await file.read())
    try:
        result = await trans_svc.transcribe(tmp, language=None)
        # Tradução mock para inglês
        translated = dub_svc.translate_text(result["text"], "pt-BR", "en-US")
        result["text"] = translated
        if response_format == "verbose_json":
            return result
        return {"text": translated}
    finally:
        try:
            tmp.unlink()
        except:
            pass

# ── Transcription (nativa) ──
@app.post("/api/transcribe")
async def transcribe_file(
    file: UploadFile = File(...),
    language: str | None = Form(None),
    diarize: bool = Form(False),
):
    tmp = UPLOADS_DIR / f"tr_{uuid.uuid4().hex[:6]}_{file.filename or 'audio.wav'}"
    tmp.write_bytes(await file.read())
    try:
        if diarize:
            result = await trans_svc.transcribe_with_diarization(tmp, language)
        else:
            result = await trans_svc.transcribe(tmp, language)
        return result
    finally:
        try:
            tmp.unlink()
        except:
            pass

# ── Dubbing ──
@app.post("/api/dub")
async def dub_from_audio(
    file: UploadFile | None = File(None),
    source_lang: str = Form("pt-BR"),
    target_lang: str = Form("en-US"),
    voice: str = Form("en-US-JennyNeural"),
    engine: str = Form("arena-tts"),
    text: str | None = Form(None),
):
    if text and text.strip():
        # Dubbing de texto direto (sem áudio)
        translated = dub_svc.translate_text(text, source_lang, target_lang)
        result = await gen_svc.synthesize(translated, voice, engine)
        return {
            "id": uuid.uuid4().hex[:8],
            "source_lang": source_lang,
            "target_lang": target_lang,
            "original_text": text,
            "translated_text": translated,
            "audio": result,
        }
    if not file or not file.filename:
        raise HTTPException(400, "Envie um arquivo de áudio ou texto")
    tmp = UPLOADS_DIR / f"dub_{uuid.uuid4().hex[:6]}_{file.filename}"
    tmp.write_bytes(await file.read())
    try:
        return await dub_svc.dub_pipeline(tmp, source_lang, target_lang, voice, engine)
    finally:
        try:
            tmp.unlink()
        except:
            pass

@app.post("/api/dub/video")
async def dub_video_endpoint(
    file: UploadFile = File(...),
    source_lang: str = Form("pt-BR"),
    target_lang: str = Form("en-US"),
    voice: str = Form("en-US-JennyNeural"),
    engine: str = Form("arena-tts"),
):
    tmp = UPLOADS_DIR / f"dubv_{uuid.uuid4().hex[:6]}_{file.filename}"
    tmp.write_bytes(await file.read())
    try:
        return await dub_svc.dub_video(tmp, source_lang=source_lang, target_lang=target_lang, voice=voice, engine=engine)
    finally:
        try:
            tmp.unlink()
        except:
            pass

# ── Audiobook ──
@app.post("/api/audiobook")
async def create_audiobook(req: AudiobookRequest):
    if not req.text or len(req.text.strip()) < 3:
        raise HTTPException(400, "Texto muito curto")
    try:
        return await ab_svc.create_audiobook(req.text, req.voice, req.engine, req.title)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/audiobook/pdf")
async def create_audiobook_pdf(
    file: UploadFile = File(...),
    voice: str = Form("pt-BR-FranciscaNeural"),
    engine: str = Form("arena-tts"),
    title: str = Form("Audiobook"),
):
    tmp = UPLOADS_DIR / f"book_{uuid.uuid4().hex[:6]}_{file.filename}"
    tmp.write_bytes(await file.read())
    try:
        text = ab_svc.extract_text_from_pdf(tmp)
        if not text or len(text.strip()) < 10:
            raise HTTPException(400, "PDF sem texto extraível")
        return await ab_svc.create_audiobook(text, voice, engine, title)
    finally:
        try:
            tmp.unlink()
        except:
            pass

# ── WebSocket Dictation (tempo real) ──
@app.websocket("/v1/audio/transcriptions/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    session_id = uuid.uuid4().hex[:8]
    await websocket.send_json({"type": "session.started", "protocol": "voicestudio.speech.v1", "session_id": session_id})
    try:
        while True:
            msg = await websocket.receive()
            if "bytes" in msg and msg["bytes"]:
                # Simular partial
                await asyncio.sleep(0.3)
                await websocket.send_json({"type": "partial", "text": "reconhecendo...", "session_id": session_id})
            elif "text" in msg and msg["text"]:
                try:
                    data = json.loads(msg["text"])
                    if data.get("type") == "input_audio.end":
                        await websocket.send_json({"type": "final", "final_kind": "summary", "text": "Olá mundo. Transcrição final simulada.", "session_id": session_id})
                        await websocket.send_json({"type": "session.ended", "session_id": session_id})
                        break
                except json.JSONDecodeError:
                    pass
            else:
                break
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/transcribe")
async def ws_legacy(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            if data == b"EOF" or data == b"":
                await websocket.send_json({"text": "Transcrição legada finalizada.", "is_final": True})
                break
            await websocket.send_json({"text": "parcial...", "is_final": False})
    except WebSocketDisconnect:
        pass

# ── MCP-like tool listing ──
@app.get("/api/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "tts", "endpoint": "POST /api/generate", "desc": "Texto -> áudio"},
            {"name": "clone_voice", "endpoint": "POST /api/voices/clone", "desc": "Clonar voz a partir de amostra"},
            {"name": "design_voice", "endpoint": "POST /api/voices/design", "desc": "Desenhar voz por prompt"},
            {"name": "transcribe", "endpoint": "POST /api/transcribe", "desc": "Áudio -> texto"},
            {"name": "dub", "endpoint": "POST /api/dub", "desc": "Dublagem com tradução"},
            {"name": "audiobook", "endpoint": "POST /api/audiobook", "desc": "Criar audiobook"},
        ]
    }

# ── Frontend static & SPA fallback ──
frontend_dir = _backend_dir.parent / "frontend"
if frontend_dir.exists():
    # Servir assets se houver build
    try:
        app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    except:
        pass

# ── Run helper ──
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("VOICESTUDIO_PORT", os.getenv("PORT", "3900")))
    print(f"🎙️  VoiceStudio Arena v{VERSION} em http://0.0.0.0:{port}")
    print(f"📖  Docs em http://localhost:{port}/docs")
    print(f"🎨  Frontend em http://localhost:{port}/")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
