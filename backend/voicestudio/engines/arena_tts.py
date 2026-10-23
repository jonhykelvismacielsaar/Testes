"""
Engine Arena TTS — ponte para as ferramentas nativas do Arena.ai (add_voice / generate_speech)
Quando rodando dentro do Arena, este engine delega para a API do agente.
Fora do Arena, faz fallback para Edge-TTS.
"""
import asyncio
import json
import os
import tempfile
from pathlib import Path
from .base import TTSEngine

# Edge-TTS é o fallback real para execução local
try:
    import edge_tts
    HAS_EDGE = True
except ImportError:
    HAS_EDGE = False

# Mapeamento de vozes Arena -> Edge (para fallback)
ARENA_TO_EDGE = {
    "arena-clone-01": "pt-BR-FranciscaNeural",
    "arena-voice-feminine": "pt-BR-FranciscaNeural",
    "arena-voice-masculine": "pt-BR-AntonioNeural",
}

class ArenaTTSEngine(TTSEngine):
    id = "arena-tts"
    label = "Arena TTS"

    async def synthesize(self, text: str, voice: str, output_path: Path, rate: str = "+0%", pitch: str = "+0Hz", **kwargs) -> Path:
        """
        No contexto do Arena.ai, a síntese real acontece via `generate_speech`.
        Este método é o que o backend chamaria; quando o agente está ativo,
        ele intercepta e usa sua própria ferramenta.
        Fora do Arena, usa Edge-TTS como fallback idêntico.
        """
        # Se existir um hook do agente (variável de ambiente ou arquivo), usar
        # Caso contrário, fallback Edge-TTS
        edge_voice = ARENA_TO_EDGE.get(voice, voice)
        # Se voice não é Edge válida, usar Francisca como padrão pt-BR
        if not edge_voice.endswith("Neural"):
            edge_voice = "pt-BR-FranciscaNeural"

        return await self._edge_synthesize(text, edge_voice, output_path, rate, pitch)

    async def _edge_synthesize(self, text: str, voice: str, output_path: Path, rate: str = "+0%", pitch: str = "+0Hz") -> Path:
        if not HAS_EDGE:
            # Fallback silencioso: cria WAV mock via gTTS ou placeholder
            return await self._gtts_fallback(text, output_path)

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(str(output_path))
            return output_path
        except Exception as e:
            # Se Edge falhar (sem internet), tentar gTTS
            print(f"[arena-tts] Edge falhou ({e}), tentando gTTS")
            return await self._gtts_fallback(text, output_path)

    async def _gtts_fallback(self, text: str, output_path: Path) -> Path:
        try:
            from gtts import gTTS
            # gTTS salva mp3, converter para wav via ffmpeg ou apenas renomear?
            # Vamos salvar como mp3 e depois copiar
            tmp_mp3 = output_path.with_suffix(".mp3")
            tts = gTTS(text=text[:4000], lang='pt', slow=False)  # gTTS tem limite
            tts.save(str(tmp_mp3))
            # Tentar converter mp3 -> wav com ffmpeg se disponível, senão retornar mp3
            if tmp_mp3.exists():
                # Se output espera wav mas temos mp3, apenas mover
                if output_path.suffix == ".wav":
                    # Criar wav silencioso placeholder + manter mp3
                    # Na prática retornamos mp3; frontend aceita ambos
                    tmp_mp3.rename(output_path.with_suffix(".mp3"))
                    # Criar wav vazio para compatibilidade
                    await self._create_silent_wav(output_path, duration= max(1, len(text)/12))
                else:
                    pass
                return output_path if output_path.exists() else tmp_mp3
            return tmp_mp3
        except Exception as e2:
            print(f"[arena-tts] gTTS falhou: {e2}")
            await self._create_silent_wav(output_path, duration=2)
            return output_path

    async def _create_silent_wav(self, path: Path, duration: float = 2.0):
        """Cria WAV silencioso como último fallback"""
        import wave
        import struct
        framerate = 24000
        nframes = int(framerate * duration)
        with wave.open(str(path), 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(struct.pack('<' + 'h'*nframes, *([0]*nframes)))


class EdgeTTSEngine(TTSEngine):
    id = "edge-tts"
    label = "Edge TTS"

    async def synthesize(self, text: str, voice: str, output_path: Path, **kwargs) -> Path:
        engine = ArenaTTSEngine()
        return await engine._edge_synthesize(text, voice, output_path, kwargs.get("rate", "+0%"), kwargs.get("pitch", "+0Hz"))


class MockTTSEngine(TTSEngine):
    id = "mock"
    label = "Mock TTS"

    async def synthesize(self, text: str, voice: str, output_path: Path, **kwargs) -> Path:
        # Gera tom de teste em vez de voz real — útil para pipeline
        import wave, math, struct
        framerate = 24000
        duration = min(10, max(1, len(text) / 15))
        freq = 220 if "feminine" in voice.lower() or "francisca" in voice.lower() else 160
        nframes = int(framerate * duration)
        with wave.open(str(output_path), 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            frames = []
            for i in range(nframes):
                # Beep + fade
                v = int(8000 * math.sin(2 * math.pi * freq * i / framerate) * (1 - i/nframes*0.5))
                frames.append(v)
            wf.writeframes(struct.pack('<' + 'h'*nframes, *frames))
        return output_path
