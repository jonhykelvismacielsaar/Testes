#!/usr/bin/env python3
"""Launcher compatível com VoiceStudio: python run.py"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))
from main import app
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("VOICESTUDIO_PORT", os.getenv("PORT", "3900")))
    print(f"🎙️  VoiceStudio Arena — http://0.0.0.0:{port}")
    print(f"📖  Docs: http://localhost:{port}/docs")
    print(f"🎨  UI:   http://localhost:{port}/")
    uvicorn.run(app, host="0.0.0.0", port=port)
