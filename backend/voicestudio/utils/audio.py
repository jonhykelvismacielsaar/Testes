"""
Utilitários de áudio/vídeo do VoiceStudio Arena.

Objetivo principal: permitir que uma amostra de voz seja extraída de um
**vídeo** (ex.: selfie gravada no celular), limpa e normalizada, pronta para
clonagem — resolvendo o caso em que o chat só aceita imagem/vídeo.

Requer ffmpeg. Se o binário do sistema não existir, usa o que vem embutido
no pacote `imageio-ffmpeg` (pip install imageio-ffmpeg).
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Optional

VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".wmv", ".flv",
    ".mpeg", ".mpg", ".3gp", ".ts", ".ogv",
}
AUDIO_EXTS = {
    ".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".wma", ".aiff", ".aif", ".amr", ".webm",
}


# --------------------------------------------------------------------------- #
# ffmpeg / ffprobe
# --------------------------------------------------------------------------- #
def ffmpeg_exe() -> Optional[str]:
    """Caminho do ffmpeg: sistema primeiro, senão o embutido do imageio-ffmpeg."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def has_ffmpeg() -> bool:
    return ffmpeg_exe() is not None


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


_DUR_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_STREAM_RE = re.compile(r"Stream #\d+:\d+.*?:\s*(Video|Audio):\s*([A-Za-z0-9_]+)")


def probe_media(path: str | Path) -> dict:
    """
    Inspeção simples via `ffmpeg -i` (funciona sem ffprobe).
    Retorna duration, has_video, has_audio, codecs, sample_rate, channels.
    """
    path = Path(path)
    info = {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "duration": 0.0,
        "has_video": False,
        "has_audio": False,
        "video_codec": None,
        "audio_codec": None,
        "sample_rate": None,
        "channels": None,
        "is_video": path.suffix.lower() in VIDEO_EXTS,
    }
    exe = ffmpeg_exe()
    if not exe or not path.exists():
        return info
    proc = _run([exe, "-hide_banner", "-i", str(path)], timeout=60)
    stderr = proc.stderr or ""
    m = _DUR_RE.search(stderr)
    if m:
        h, mi, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mi) * 60 + float(s)
    for kind, codec in _STREAM_RE.findall(stderr):
        if kind == "Video":
            info["has_video"] = True
            info["video_codec"] = codec
        else:
            info["has_audio"] = True
            info["audio_codec"] = codec
    m = re.search(r"(\d{4,6}) Hz,\s*([a-z]+)", stderr)
    if m:
        info["sample_rate"] = int(m.group(1))
        info["channels"] = m.group(2)
    info["is_video"] = info["has_video"] or info["is_video"]
    return info


# --------------------------------------------------------------------------- #
# Extração / limpeza de voz
# --------------------------------------------------------------------------- #
# Cadeia de filtros: corta graves/agudos inúteis, reduz ruído de fundo,
# normaliza volume para nível de podcast e reamostra para 24 kHz mono.
VOICE_FILTERS = (
    "highpass=f=80,"
    "lowpass=f=10000,"
    "afftdn=nr=12:nf=-30:tn=1,"
    "loudnorm=I=-16:TP=-1.5:LRA=11,"
    "aresample=24000"
)

SIMPLE_FILTERS = "highpass=f=80,lowpass=f=10000,aresample=24000"


def extract_voice(
    src: str | Path,
    dst: str | Path,
    start: Optional[float] = None,
    duration: Optional[float] = None,
    denoise: bool = True,
    normalize: bool = True,
    target_sr: int = 24000,
) -> dict:
    """
    Extrai a faixa de voz de um vídeo/áudio e grava um WAV mono pronto para clonar.

    - start/duration: recorte em segundos (ex.: pegar só 20s a partir de 0:05)
    - denoise: remove ruído de fundo (afftdn)
    - normalize: loudness EBU R128 (-16 LUFS)
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError(
            "ffmpeg não encontrado. Instale com: pip install imageio-ffmpeg "
            "(ou apt install ffmpeg)."
        )
    if not src.exists() or src.stat().st_size == 0:
        raise FileNotFoundError(f"Arquivo de entrada vazio ou inexistente: {src}")

    info = probe_media(src)
    if not info["has_audio"]:
        raise ValueError(
            "O arquivo enviado não tem faixa de áudio. Grave um vídeo falando "
            "(a câmera pode estar tampada, só o microfone importa)."
        )

    if denoise and normalize:
        filters = VOICE_FILTERS
    elif normalize:
        filters = "highpass=f=80,lowpass=f=10000,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=24000"
    elif denoise:
        filters = "highpass=f=80,lowpass=f=10000,afftdn=nr=12:nf=-30:tn=1,aresample=24000"
    else:
        filters = SIMPLE_FILTERS

    filters = filters.replace("aresample=24000", f"aresample={target_sr}")

    def _cmd(filter_chain: Optional[str]) -> list[str]:
        c = [exe, "-y", "-hide_banner", "-loglevel", "error"]
        if start is not None:
            c += ["-ss", str(float(start))]
        c += ["-i", str(src)]
        if duration is not None:
            c += ["-t", str(float(duration))]
        c += ["-vn", "-sn", "-dn"]
        if filter_chain:
            c += ["-af", filter_chain]
        c += [
            "-ac", "1",
            "-ar", str(target_sr),
            "-c:a", "pcm_s16le",
            str(dst),
        ]
        return c

    last_err = ""
    # 1ª tentativa: com limpeza completa
    proc = _run(_cmd(filters))
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
        last_err = (proc.stderr or "").strip()[-800:]
        # 2ª tentativa: filtros simples (build sem afftdn/loudnorm)
        proc = _run(_cmd(SIMPLE_FILTERS))
        if proc.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
            last_err = (proc.stderr or last_err).strip()[-800:]
            # 3ª tentativa: sem filtros
            proc = _run(_cmd(None))
            if proc.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
                raise RuntimeError(f"Falha ao extrair áudio: {last_err}")

    out_info = analyze_wav(dst)
    return {
        "source": str(src),
        "output": str(dst),
        "source_info": info,
        "output_info": out_info,
        "applied": {
            "start": start,
            "duration": duration,
            "denoise": denoise,
            "normalize": normalize,
            "sample_rate": target_sr,
        },
    }


def convert_to_wav(src: str | Path, dst: str | Path, sample_rate: int = 24000) -> Path:
    """Conversão simples (sem limpeza) para WAV mono."""
    extract_voice(src, dst, denoise=False, normalize=False, target_sr=sample_rate)
    return Path(dst)


def analyze_wav(path: str | Path) -> dict:
    """Métricas básicas do WAV: duração, pico, RMS e avisos de qualidade."""
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as wf:
            nch = wf.getnchannels()
            sr = wf.getframerate()
            sw = wf.getsampwidth()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)
    except Exception as e:
        return {"path": str(path), "error": str(e)}

    duration = nframes / sr if sr else 0.0
    peak = 0
    rms = 0.0
    if sw == 2 and raw:
        import array
        samples = array.array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if samples:
            peak = max(abs(min(samples)), abs(max(samples)))
            step = max(1, len(samples) // 20000)
            sub = samples[::step]
            rms = math.sqrt(sum(float(s) * s for s in sub) / max(1, len(sub)))

    peak_db = 20 * math.log10(max(peak / 32768.0, 1e-6)) if peak else -120.0
    rms_db = 20 * math.log10(max(rms / 32768.0, 1e-6)) if rms else -120.0

    warnings = []
    if duration < 3:
        warnings.append("Amostra MUITO curta (<3s). Grave pelo menos 10 segundos falando.")
    elif duration < 8:
        warnings.append("Amostra curta. O ideal é 15–30 segundos de fala contínua.")
    if peak >= 32700:
        warnings.append("Áudio saturado (clipping). Grave um pouco mais longe do microfone.")
    if rms_db < -45:
        warnings.append("Volume muito baixo. Aproxime-se do microfone.")
    if duration > 180:
        warnings.append("Amostra longa (>3min). Para clonagem, 15–30s já bastam.")

    return {
        "path": str(path),
        "duration": round(duration, 2),
        "sample_rate": sr,
        "channels": nch,
        "peak": peak,
        "peak_db": round(peak_db, 1),
        "rms_db": round(rms_db, 1),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "warnings": warnings,
        "ok": duration >= 3 and peak > 500,
    }


def is_supported_media(path: str | Path) -> bool:
    return Path(path).suffix.lower() in (VIDEO_EXTS | AUDIO_EXTS)


def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)

# --------------------------------------------------------------------------- #
# Perfil de voz (F0 / ritmo) — usado para casar o tom da voz sintetizada
# --------------------------------------------------------------------------- #
def estimate_voice_profile(path: str | Path) -> dict:
    """
    Estima características da voz de uma amostra: F0 (tom fundamental) mediana,
    faixa de F0, energia e velocidade de fala aproximada.

    Não é clonagem neural — é uma medição acústica usada para ajustar tom e
    velocidade de uma voz sintética (pitch/rate).
    """
    path = Path(path)
    out = {
        "path": str(path),
        "f0_median": None,
        "f0_min": None,
        "f0_max": None,
        "f0_range_semitones": None,
        "suggested_pitch": 1.0,
        "suggested_rate": 1.0,
        "gender_hint": None,
        "duration": 0.0,
        "voiced_ratio": 0.0,
        "note": "Medição acústica — não é clonagem neural.",
    }
    try:
        import numpy as np
    except ImportError:
        out["error"] = "numpy não instalado"
        return out

    tmp = Path(str(path)).with_suffix(".f0.wav")
    try:
        if path.suffix.lower() != ".wav" or True:
            extract_voice(path, tmp, denoise=True, normalize=False, target_sr=16000)
            work = tmp
        else:
            work = path
        with wave.open(str(work), "rb") as wf:
            sr = wf.getframerate()
            n = wf.getnframes()
            raw = wf.readframes(n)
        if not raw:
            raise ValueError("áudio vazio")
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        out["duration"] = round(len(samples) / sr, 2)

        frame = int(0.04 * sr)      # 40 ms
        hop = int(0.02 * sr)        # 20 ms
        f0s: list[float] = []
        energy: list[float] = []
        for start in range(0, max(0, len(samples) - frame), hop):
            chunk = samples[start:start + frame]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            energy.append(rms)
            if rms < 0.01:            # silêncio
                continue
            chunk = chunk - np.mean(chunk)
            corr = np.correlate(chunk, chunk, mode="full")[len(chunk) - 1:]
            if corr[0] <= 1e-9:
                continue
            corr = corr / corr[0]
            min_lag = int(sr / 400)   # 400 Hz
            max_lag = int(sr / 60)    # 60 Hz
            if max_lag >= len(corr):
                continue
            window = corr[min_lag:max_lag]
            if len(window) == 0:
                continue
            peak_idx = int(np.argmax(window))
            if window[peak_idx] < 0.35:   # pouca periodicidade -> sem voz
                continue
            f0s.append(sr / (min_lag + peak_idx))

        if f0s:
            arr = np.array(f0s)
            med = float(np.median(arr))
            p10, p90 = float(np.percentile(arr, 10)), float(np.percentile(arr, 90))
            out.update({
                "f0_median": round(med, 1),
                "f0_min": round(p10, 1),
                "f0_max": round(p90, 1),
                "f0_range_semitones": round(12 * float(np.log2(max(p90, 1) / max(p10, 1))), 1),
                "voiced_ratio": round(len(f0s) / max(1, len(energy)), 3),
            })
            # heurística: voz típica de referência ~ 165 Hz
            ratio = med / 165.0
            out["suggested_pitch"] = round(min(1.6, max(0.6, ratio ** 0.5)), 2)
            out["gender_hint"] = "masculine" if med < 140 else "feminine" if med > 175 else "neutral"
        # ritmo: pausas longas (>250ms de silêncio) por minuto
        if energy:
            e = np.array(energy)
            thr = max(0.01, float(np.percentile(e, 30)) * 0.6)
            sil = e < thr
            runs, cur = [], 0
            for v in sil:
                if v:
                    cur += 1
                elif cur:
                    runs.append(cur * (hop / sr)); cur = 0
            if cur:
                runs.append(cur * (hop / sr))
            pauses = [r for r in runs if r > 0.25]
            per_min = len(pauses) / max(0.1, out["duration"] / 60)
            out["pauses_per_minute"] = round(per_min, 1)
            if per_min > 22:
                out["suggested_rate"] = 0.85
            elif per_min < 8:
                out["suggested_rate"] = 1.1
        return out
    except Exception as e:
        out["error"] = str(e)
        return out
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
