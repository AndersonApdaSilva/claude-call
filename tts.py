"""TTS via Microsoft edge-tts (gratis, online, vozes neurais em varios idiomas).

Pipecat nao traz edge-tts embutido, entao implementamos um TTSService:
edge-tts gera MP3 -> ffmpeg decodifica pra PCM s16le mono -> frames de audio raw.
"""
import asyncio
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
