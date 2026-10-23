"""
Ponte entre o backend VoiceStudio Arena e as ferramentas nativas do Arena.ai

Este módulo permite que o agente Arena use as funcionalidades do VoiceStudio
diretamente via `add_voice` e `generate_speech`, sem precisar chamar HTTP.

Uso dentro do agente (python):

    from backend.voicestudio.arena_bridge import ArenaVoiceBridge
    bridge = ArenaVoiceBridge(add_voice_fn=add_voice, generate_speech_fn=generate_speech)

    # Clonar voz a partir de texto descritivo
    voice_id = await bridge.clone_voice_from_prompt("voz feminina calorosa brasileira", lang="pt-BR")

    # Gerar fala
    path = await bridge.speak("Olá, bem-vindo ao VoiceStudio Arena!", voice_id=voice_id)

A classe também gera instruções em linguagem natural que o agente pode seguir
quando as funções Python não estão disponíveis (ex: só via tool-calling).
"""

from pathlib import Path
from typing import Optional

class ArenaVoiceBridge:
    """
    Adapta as ferramentas do Arena (add_voice / generate_speech) para a interface VoiceStudio.
    """

    # Mapeamento de idiomas -> voz padrão Arena simulada
    DEFAULT_VOICES = {
        "pt-BR": {"gender": "feminine", "sample": "Olá, eu sou uma voz brasileira natural do VoiceStudio Arena."},
        "en-US": {"gender": "feminine", "sample": "Hello, I'm a natural US voice from VoiceStudio Arena."},
        "es-ES": {"gender": "feminine", "sample": "Hola, soy una voz española natural de VoiceStudio Arena."},
        "fr-FR": {"gender": "feminine", "sample": "Bonjour, je suis une voix française naturelle."},
        "ja-JP": {"gender": "feminine", "sample": "こんにちは、VoiceStudio Arenaのナチュラルな声です。"},
    }

    PROMPT = """
Você é o VoiceStudio Arena — um estúdio de clonagem e geração de voz.

Ferramentas disponíveis neste ambiente:
- add_voice(text, language, gender/use_case) → registra uma voz e retorna voice_id
- generate_speech(file_path, text, voice_id) → sintetiza áudio

Fluxos:
1. **Clonar voz por amostra textual**: A usuária descreve a voz → você chama add_voice com essa descrição como `text` e escolhe gender/use_case.
2. **Gerar fala**: Recebe texto + estilo → chama generate_speech com voice_id.
3. **Dublar**: Transcreve (se houver áudio) → traduz → gera com nova voz.
4. **Audiobook**: Quebra texto em capítulos e gera cada um.

Sempre que o usuário pedir voz/áudio, use add_voice + generate_speech diretamente.
"""

    def __init__(self, add_voice_fn=None, generate_speech_fn=None):
        self.add_voice = add_voice_fn
        self.generate_speech = generate_speech_fn
        self._voice_cache = {}

    async def clone_voice_from_prompt(self, description: str, language: str = "pt-BR", gender: str = "feminine") -> str:
        """Cria voz a partir de descrição textual (voice design)."""
        if not self.add_voice:
            raise RuntimeError("add_voice não disponível — rode dentro do Arena.ai")
        # add_voice espera um text que as vozes candidatas vão falar; usamos a descrição como audition
        # A linguagem deve bater com o texto
        voice_id = await self.add_voice(
            text=description[:200],  # audition text
            language=language,
            voice_identity={"gender": gender, "use_case": "narration"}
        ) if callable(self.add_voice) else self.add_voice(description, language)
        self._voice_cache[description] = voice_id
        return voice_id

    async def speak(self, text: str, voice_id: str, output_path: str = "output.mp3", language: Optional[str] = None) -> str:
        if not self.generate_speech:
            raise RuntimeError("generate_speech não disponível")
        await self.generate_speech(file_path=output_path, text=text, voice_id=voice_id, language=language)
        return output_path

    async def dub_text(self, text: str, source_lang: str, target_lang: str, voice_id: str, output_path: str = "dubbed.mp3") -> str:
        # Em produção usaria tradução real; aqui delega para o agente traduzir via LLM
        # O agente já traduz com conhecimento linguístico
        translated = text  # placeholder — agente deve traduzir antes de chamar
        return await self.speak(translated, voice_id, output_path, language=target_lang)

    def instructions_for_agent(self) -> str:
        return self.PROMPT

    # --- Helpers síncronos para uso via HTTP backend ---
    def describe_capabilities(self) -> dict:
        return {
            "cloning": "add_voice(text, language) → voice_id",
            "tts": "generate_speech(file_path, text, voice_id) → audio",
            "languages": list(self.DEFAULT_VOICES.keys()) + ["646 total"],
            "features": ["voice_cloning", "voice_design", "dubbing", "audiobook", "transcription", "dictation"]
        }
