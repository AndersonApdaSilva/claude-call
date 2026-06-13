"""Configuracao do claude-call (tudo via env CALL_*, com defaults sensatos)."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega o .env do repo no import, pra QUALQUER entrypoint (call, doctor) ver a config.
load_dotenv(Path(__file__).resolve().parent / ".env")

# Audio
SAMPLE_RATE_IN = 16000    # Silero VAD so aceita 8k/16k; whisper tambem quer 16k
SAMPLE_RATE_OUT = 24000   # edge-tts

LANG = os.getenv("CALL_LANG", "en")

# Voz default por idioma (edge-tts). Sobrescreva com CALL_VOICE.
_DEFAULT_VOICE = {
    "en": "en-US-AndrewNeural",
    "pt": "pt-BR-AntonioNeural",
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "ja": "ja-JP-KeitaNeural",
}
# TTS provider: edge (free, default) | elevenlabs | cartesia | openai | rime | deepgram
TTS = os.getenv("CALL_TTS", "edge").lower()
TTS_API_KEY = os.getenv("CALL_TTS_API_KEY") or None
TTS_MODEL = os.getenv("CALL_TTS_MODEL") or None

# Voice: for edge, fall back to a per-language default. For premium providers, leave
# it as set (a provider voice id) — the factory picks a sensible default if empty.
EDGE_VOICE = _DEFAULT_VOICE.get(LANG[:2], "en-US-AndrewNeural")  # free fallback voice
_raw_voice = os.getenv("CALL_VOICE") or None
if TTS == "edge":
    VOICE = _raw_voice or EDGE_VOICE
else:
    VOICE = _raw_voice
VOICE_RATE = os.getenv("CALL_VOICE_RATE", "+0%")

# Saudacao inicial por idioma
_GREETING = {
    "en": "Hey, I'm here. What's up?",
    "pt": "Opa, tô na linha. Pode falar.",
    "es": "Hola, estoy aquí. Dime.",
}
GREETING = os.getenv("CALL_GREETING") or _GREETING.get(LANG[:2], _GREETING["en"])

# Cerebro (Claude Code). Vazio = herda o modelo padrao do seu Claude Code.
MODEL = os.getenv("CALL_MODEL") or None
# Permissoes do agente headless. Hands-free precisa nao travar em prompt.
# ATENCAO: skip-permissions deixa o agente rodar tools/bash sem perguntar. Veja o README.
PERMISSION = os.getenv("CALL_PERMISSION", "--dangerously-skip-permissions")

# Sessao: continua a SUA conversa mais recente desse diretorio (o diferencial).
CONTINUE = os.getenv("CALL_CONTINUE", "1") not in ("0", "false", "no")
SESSION_ID = os.getenv("CALL_SESSION_ID") or None
CWD = os.getenv("CALL_CWD") or os.getcwd()

# Ativacao: vazio = mic aberto (modo call). Preencha pra exigir wake word.
WAKE = [w for w in os.getenv("CALL_WAKE", "").split(",") if w.strip()]
ACTIVE_WINDOW = float(os.getenv("CALL_ACTIVE_WINDOW", "25"))

# Anti-eco
ECHO_GATE = os.getenv("CALL_ECHO_GATE", "1") not in ("0", "false", "no")
AEC = os.getenv("CALL_AEC", "0") not in ("0", "false", "no")

# STT (whisper.cpp)
WHISPER_MODEL = os.path.expanduser(os.getenv(
    "CALL_WHISPER_MODEL", str(Path.home() / ".cache" / "whisper" / "ggml-small.bin")
))
WHISPER_PORT = int(os.getenv("CALL_WHISPER_PORT", "8099"))
USE_WHISPER_SERVER = os.getenv("CALL_WHISPER_SERVER", "1") not in ("0", "false", "no")

# Quanto tempo de SILENCIO antes da call se encerrar sozinha (segundos).
# "0"/"off" = nunca encerra por inatividade (so Ctrl+C ou "encerrar"). Default 30 min.
IDLE_TIMEOUT = os.getenv("CALL_IDLE_TIMEOUT", "1800")


# Regras de fala (system prompt apensado a cada turno). Mantem a resposta "de call".
_VOICE_RULES = {
    "en": (
        "You are on a live VOICE call — not coding, not writing a report. Talk like a "
        "real person on a phone call: relaxed, warm, casual, contracted. Keep it SHORT, "
        "1-2 sentences, the way it actually comes out in conversation. "
        "Do NOT narrate what you're doing internally — no 'let me edit the file', 'running "
        "the command', 'opening the code', 'checking the skill'. Nobody talks like that on a "
        "call; just deliver the result, naturally. "
        "NEVER read aloud: markdown, lists, code blocks, URLs, file paths, IDs, hashes, or "
        "long numbers. If you must hand over something written, summarize it in speech. "
        "No assistant filler ('how can I help', 'understood', 'certainly!'). If you don't "
        "know yet, say something natural like 'hold on, let me check that'. "
        "GOLDEN RULE: when in doubt, SIMPLIFY. Fewer words, more human."
    ),
    "pt": (
        "Voce esta numa LIGACAO de voz, em tempo real — nao esta codando nem escrevendo "
        "relatorio. Fale como gente numa call: solto, caloroso, informal, contraido (to, pra, "
        "ce, ta, ne). Curto, 1 a 2 frases, do jeito que sai na conversa. "
        "NAO narre o que esta fazendo por dentro ('vou editar', 'rodando o comando'). So "
        "entrega o resultado, natural. NUNCA leia markdown, listas, codigo, URLs, caminhos, "
        "IDs ou numeros longos. Sem bordao de assistente. Na duvida, SIMPLIFIQUE."
    ),
}
VOICE_RULES = os.getenv("CALL_SYSTEM") or _VOICE_RULES.get(LANG[:2], _VOICE_RULES["en"])
WHISPER_LANG = LANG[:2]
