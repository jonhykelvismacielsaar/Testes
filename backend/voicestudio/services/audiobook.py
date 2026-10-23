from pathlib import Path
import uuid
import re
import json
from datetime import datetime
from ..config import OUTPUTS_DIR
from .generation import synthesize

def split_into_chapters(text: str, max_chars: int = 2000) -> list:
    """Divide texto em capítulos/chunks para TTS"""
    # Tenta quebrar por parágrafos e capítulos marcados
    # Detecta "Capítulo 1", "Chapter 1", "## ", etc.
    chapter_pattern = re.compile(r'(?m)^(#+\s+|Capítulo\s+\d+|Chapter\s+\d+|CAPÍTULO\s+\d+)')
    parts = chapter_pattern.split(text)
    chapters = []
    if len(parts) > 1:
        # Tem marcadores
        for i in range(1, len(parts), 2):
            title = parts[i].strip()
            body = parts[i+1] if i+1 < len(parts) else ""
            body = (title + "\n" + body).strip()
            # Quebrar capítulos muito longos
            for chunk in chunk_text(body, max_chars):
                chapters.append(chunk)
    else:
        chapters = chunk_text(text, max_chars)

    return [{"index": i+1, "title": f"Capítulo {i+1}", "text": c} for i, c in enumerate(chapters)]

def chunk_text(text: str, max_chars: int) -> list:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    # Quebra por frases
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current += (" " if current else "") + s
        else:
            if current:
                chunks.append(current)
            if len(s) > max_chars:
                # Frase gigante: quebra forçada
                for i in range(0, len(s), max_chars):
                    chunks.append(s[i:i+max_chars])
                current = ""
            else:
                current = s
    if current:
        chunks.append(current)
    return chunks

def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n\n"
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"Falha ao ler PDF: {e}")

async def create_audiobook(text: str, voice: str, engine: str = "arena-tts", title: str = "Audiobook") -> dict:
    book_id = uuid.uuid4().hex[:8]
    chapters = split_into_chapters(text, max_chars=1800)

    # Limitar para demo: máx 5 capítulos por requisição (evitar custo excessivo)
    limited = chapters[:5]
    if len(chapters) > 5:
        note = f"Texto muito longo ({len(chapters)} capítulos). Gerando primeiros 5. Use batch para o restante."
    else:
        note = None

    audios = []
    for ch in limited:
        res = await synthesize(ch["text"], voice, engine_id=engine)
        audios.append({
            "chapter": ch["index"],
            "title": ch["title"],
            "text": ch["text"][:120] + "...",
            "audio": res
        })

    return {
        "id": book_id,
        "title": title,
        "total_chapters": len(chapters),
        "generated_chapters": len(audios),
        "chapters": audios,
        "note": note,
        "created_at": datetime.utcnow().isoformat(),
    }
