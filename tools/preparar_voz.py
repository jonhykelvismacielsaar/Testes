#!/usr/bin/env python3
"""
Prepara uma amostra de voz a partir de VÍDEO ou áudio, pronta para clonagem.

Use quando o seu chat só permite enviar vídeo (ou quando a gravação veio de
celular, com ruído de fundo).

Exemplos
--------
# 20 segundos a partir do início, com limpeza e normalização
python3 tools/preparar_voz.py meu-video.mp4 -o data/uploads/minha_voz.wav -d 20

# começar em 0:05 e pegar 15 segundos
python3 tools/preparar_voz.py video.mov -o minha_voz.wav -i 5 -d 15

# sem remoção de ruído (mantém o som original)
python3 tools/preparar_voz.py audio.m4a -o minha_voz.wav --sem-limpeza

Saída: WAV mono 24 kHz, -16 LUFS, pronto para `POST /api/voices/clone`.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from voicestudio.utils.audio import (  # noqa: E402
    extract_voice, probe_media, has_ffmpeg, VIDEO_EXTS, AUDIO_EXTS
)


SKIP_DIRS = {".git", "node_modules", "__pycache__", "outputs", "dist", ".venv", "venv"}
SCAN_ROOTS = [Path.cwd(), Path.home() / "Testes" / "data" / "uploads", Path.home()]


def find_latest_media(max_age_hours: float = 24, roots=None) -> Path | None:
    """Procura o vídeo/áudio mais recente no workspace (útil para anexos do chat)."""
    cutoff = time.time() - max_age_hours * 3600
    best: tuple[float, Path] | None = None
    for root in (roots or SCAN_ROOTS):
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for name in filenames:
                f = Path(dirpath) / name
                if f.suffix.lower() not in (VIDEO_EXTS | AUDIO_EXTS):
                    continue
                try:
                    st = f.stat()
                except OSError:
                    continue
                if st.st_size < 20_000 or st.st_mtime < cutoff:
                    continue
                if best is None or st.st_mtime > best[0]:
                    best = (st.st_mtime, f)
    return best[1] if best else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extrai e limpa a voz de um vídeo/áudio para clonagem."
    )
    ap.add_argument("entrada", nargs="?", help="arquivo de vídeo/áudio ou pasta (padrão: mais recente)")
    ap.add_argument("-o", "--saida", default=None, help="WAV de saída (padrão: <nome>_voz.wav)")
    ap.add_argument("-i", "--inicio", type=float, default=None, help="segundo inicial (ex: 5)")
    ap.add_argument("-d", "--duracao", type=float, default=None, help="duração em segundos (ex: 20)")
    ap.add_argument("--sem-limpeza", action="store_true", help="não remove ruído nem normaliza")
    ap.add_argument("--json", action="store_true", help="imprime só o JSON")
    ap.add_argument("--ultimo", action="store_true",
                    help="ignora 'entrada' e usa o vídeo/áudio mais recente do workspace")
    args = ap.parse_args()

    if args.ultimo or not args.entrada:
        found = find_latest_media()
        if not found:
            print("❌ Nenhum vídeo/áudio recente encontrado. Passe o caminho do arquivo.", file=sys.stderr)
            return 2
        print(f"🔎 Anexo mais recente: {found}")
        src = found
    else:
        src = Path(args.entrada).expanduser()
        if src.is_dir():
            found = find_latest_media(roots=[src])
            if not found:
                print(f"❌ Nenhum vídeo/áudio recente em {src}", file=sys.stderr)
                return 2
            src = found

    if not src.exists():
        print(f"❌ Arquivo não encontrado: {src}", file=sys.stderr)
        return 2
    if src.suffix.lower() not in (VIDEO_EXTS | AUDIO_EXTS):
        print(f"⚠️  Extensão {src.suffix} incomum — tentando mesmo assim.")

    if not has_ffmpeg():
        print("❌ ffmpeg não encontrado. Rode: pip install imageio-ffmpeg", file=sys.stderr)
        return 3

    dst = Path(args.saida) if args.saida else src.with_name(f"{src.stem}_voz.wav")
    info = probe_media(src)
    if not args.json:
        tipo = "vídeo" if info["has_video"] else "áudio"
        print(f"🎬 Fonte: {src.name} ({tipo}, {info['duration']:.1f}s, "
              f"codec {info['video_codec'] or info['audio_codec'] or '?'})")
        if not info["has_audio"]:
            print("❌ Esse arquivo não tem áudio. Grave um vídeo falando.", file=sys.stderr)
            return 4

    try:
        result = extract_voice(
            src, dst,
            start=args.inicio,
            duration=args.duracao,
            denoise=not args.sem_limpeza,
            normalize=not args.sem_limpeza,
        )
    except Exception as e:
        print(f"❌ Falha: {e}", file=sys.stderr)
        return 5

    out = result["output_info"]
    result["ok"] = out.get("ok", False)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"✅ Amostra pronta: {dst}")
        print(f"   duração {out.get('duration')}s | {out.get('sample_rate')} Hz | "
              f"pico {out.get('peak_db')} dB | RMS {out.get('rms_db')} dB")
        for w in out.get("warnings", []):
            print(f"   ⚠️  {w}")
        print()
        print("Agora clone a voz:")
        print(f"   curl -X POST http://localhost:3900/api/voices/clone \\")
        print(f"     -F name='Minha Voz' -F language=pt-BR -F gender=feminine \\")
        print(f"     -F sample=@{dst}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
