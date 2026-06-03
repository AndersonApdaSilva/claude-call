"""TTS via Microsoft edge-tts (gratis, online, vozes neurais em varios idiomas).

Pipecat nao traz edge-tts embutido, entao implementamos um TTSService:
edge-tts gera MP3 -> ffmpeg decodifica pra PCM s16le mono -> frames de audio raw.
"""
import asyncio
import importlib
import os
from typing import AsyncGenerator

import edge_tts
from loguru import logger

from pipecat.frames.frames import (
    ErrorFrame, Frame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame,
)
from pipecat.services.tts_service import TTSService


class EdgeTTS(TTSService):
    def __init__(self, *, voice: str, rate: str = "+0%", pitch: str = "+0Hz",
                 sample_rate: int = 24000, **kwargs):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._voice, self._rate, self._pitch = voice, rate, pitch

    def can_generate_metrics(self) -> bool:
        return False

    async def _mp3_to_pcm(self, mp3: bytes, rate: int) -> bytes:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
            "-ac", "1", "-ar", str(rate), "pipe:1",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        pcm, err = await proc.communicate(input=mp3)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg decode failed: {err.decode(errors='ignore')[:200]}")
        return pcm

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        logger.debug(f"[edge-tts] {text!r}")
        try:
            comm = edge_tts.Communicate(text, self._voice, rate=self._rate, pitch=self._pitch)
            mp3 = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    mp3.extend(chunk["data"])
            if not mp3:
                yield ErrorFrame("edge-tts returned no audio")
                return
            pcm = await self._mp3_to_pcm(bytes(mp3), self.sample_rate)
            await self.start_ttfb_metrics()
            yield TTSStartedFrame()
            frame_bytes = int(self.sample_rate * 0.02) * 2  # ~20ms
            for i in range(0, len(pcm), frame_bytes):
                yield TTSAudioRawFrame(audio=pcm[i:i + frame_bytes],
                                       sample_rate=self.sample_rate, num_channels=1)
            yield TTSStoppedFrame()
        except Exception as e:  # noqa: BLE001
            logger.exception("[edge-tts] error")
            yield ErrorFrame(f"edge-tts error: {e}")


# ---------------------------------------------------------------- providers
# Premium TTS via Pipecat's built-in services. Bring your own API key (pay-as-you-go).
# edge = free (default). Others need CALL_TTS_API_KEY (or the provider's standard env var).

# Voices that are opaque ids (must be set by the user) vs named defaults we can pick.
_PREMIUM_DEFAULTS = {
    # provider: (default_voice_or_None, default_model_or_None, env_key_name)
    "elevenlabs": ("21m00Tcm4TlvDq8ikWAM", "eleven_turbo_v2_5", "ELEVENLABS_API_KEY"),
    "cartesia":   (None,                    "sonic-2",           "CARTESIA_API_KEY"),
    "openai":     ("alloy",                 "gpt-4o-mini-tts",   "OPENAI_API_KEY"),
    "rime":       ("cove",                  "mistv2",            "RIME_API_KEY"),
    "deepgram":   ("aura-2-thalia-en",      None,                "DEEPGRAM_API_KEY"),
}

_SVC = {
    "elevenlabs": "pipecat.services.elevenlabs.tts:ElevenLabsTTSService",
    "cartesia":   "pipecat.services.cartesia.tts:CartesiaTTSService",
    "openai":     "pipecat.services.openai.tts:OpenAITTSService",
    "rime":       "pipecat.services.rime.tts:RimeTTSService",
    "deepgram":   "pipecat.services.deepgram.tts:DeepgramTTSService",
}

PROVIDERS = ["edge"] + list(_PREMIUM_DEFAULTS)


def make_tts(*, provider: str, voice: str | None, rate: str, sample_rate: int,
             api_key: str | None = None, model: str | None = None):
    """Returns a Pipecat TTS service for the chosen provider.
    edge = free/local-ish; the rest are paid APIs (bring your own key)."""
    p = (provider or "edge").lower()
    if p == "edge":
        return EdgeTTS(voice=voice or "en-US-AndrewNeural", rate=rate, sample_rate=sample_rate)

    if p not in _PREMIUM_DEFAULTS:
        raise ValueError(f"unknown CALL_TTS '{provider}'. options: {', '.join(PROVIDERS)}")

    def_voice, def_model, env_key = _PREMIUM_DEFAULTS[p]
    key = api_key or os.getenv(env_key) or os.getenv("CALL_TTS_API_KEY")
    if not key:
        raise RuntimeError(f"{p} needs an API key — set CALL_TTS_API_KEY (or {env_key}).")
    v = voice or def_voice
    if v is None:
        raise RuntimeError(f"{p} needs a voice id — set CALL_VOICE to a {p} voice.")
    m = model or def_model

    # All Pipecat TTS services share the shape: Service(api_key, sample_rate,
    # settings=Service.Settings(voice=..., model=...)). Uniform = no deprecations.
    mod, cls = _SVC[p].split(":")
    Svc = getattr(importlib.import_module(mod), cls)
    sargs = {"voice": v}
    if m:
        sargs["model"] = m
    return Svc(api_key=key, sample_rate=sample_rate, settings=Svc.Settings(**sargs))
