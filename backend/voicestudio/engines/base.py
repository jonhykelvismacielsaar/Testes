from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class TTSEngine(ABC):
    id: str = "base"
    label: str = "Base"

    @abstractmethod
    async def synthesize(self, text: str, voice: str, output_path: Path, **kwargs) -> Path:
        raise NotImplementedError

    async def health(self) -> dict:
        return {"engine": self.id, "status": "ok"}

class ASREngine(ABC):
    id: str = "base-asr"
    label: str = "Base ASR"

    @abstractmethod
    async def transcribe(self, audio_path: Path, language: Optional[str] = None) -> dict:
        raise NotImplementedError
