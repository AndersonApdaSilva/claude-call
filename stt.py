"""STT local via whisper.cpp. Usa whisper-server (modelo residente, ~0.6s/fala) e
cai pro whisper-cli (recarrega o modelo por fala, ~2s) se o server nao subir.
"""
import asyncio
import io
import os
import subprocess
import tempfile
import warnings
import wave
from pathlib import Path
from typing import AsyncGenerator

with warnings.catch_warnings():  # audioop is fine on 3.12 (pinned); silence its 3.13 notice
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

import httpx
from loguru import logger

from pipecat.frames.frames import Frame, TranscriptionFrame
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.utils.time import time_now_iso8601

WHISPER_RATE = 16000
LOG_FILE = Path(__file__).resolve().parent / "logs" / "whisper-server.log"


def _to_16k(audio: bytes, rate: int) -> bytes:
    if rate and rate != WHISPER_RATE:
        audio, _ = audioop.ratecv(audio, 2, 1, rate, WHISPER_RATE, None)
    return audio


def _wav(audio: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(WHISPER_RATE)
        w.writeframes(audio)
    return buf.getvalue()


async def ensure_server(*, model: str, host="127.0.0.1", port=8099, language="en",
                        threads=6, wait_secs=60.0) -> str:
    base = f"http://{host}:{port}"

    async def up() -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.0) as c:
                await c.get(base + "/")
            return True
        except Exception:
            return False

    if await up():
        logger.info(f"[whisper-server] already up at {base}")
        return base
    if not Path(model).exists():
        raise FileNotFoundError(f"whisper model not found: {model} (run scripts/download-model.sh)")

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logf = open(LOG_FILE, "ab")
    logger.info(f"[whisper-server] starting ({Path(model).name})...")
    subprocess.Popen(
        ["whisper-server", "-m", model, "--host", host, "--port", str(port),
         "-l", language, "-nt", "-t", str(threads)],
        stdout=logf, stderr=logf, start_new_session=True,
    )
    deadline = asyncio.get_event_loop().time() + wait_secs
    while asyncio.get_event_loop().time() < deadline:
        if await up():
            logger.info(f"[whisper-server] ready at {base}")
            return base
        await asyncio.sleep(0.5)
    raise RuntimeError(f"whisper-server did not start in {wait_secs}s (see {LOG_FILE})")


class WhisperServerSTT(SegmentedSTTService):
    def __init__(self, *, base_url: str, language="en", sample_rate=WHISPER_RATE, **kwargs):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._url = base_url.rstrip("/") + "/inference"
        self._language = language
        self._client: httpx.AsyncClient | None = None

    def can_generate_metrics(self) -> bool:
        return False

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        await self.start_ttfb_metrics()
        wav = _wav(_to_16k(audio, self.sample_rate or WHISPER_RATE))
        try:
            resp = await self._client.post(
                self._url,
                files={"file": ("a.wav", wav, "audio/wav")},
                data={"language": self._language, "response_format": "json",
                      "no_timestamps": "true", "temperature": "0"},
            )
            text = " ".join(resp.json().get("text", "").split()).strip()
        except Exception as e:  # noqa: BLE001
            logger.error(f"[whisper-server] inference failed: {e}")
            return
        if text:
            logger.debug(f"[whisper-server] -> {text!r}")
            yield TranscriptionFrame(text, "user", time_now_iso8601())


class WhisperCliSTT(SegmentedSTTService):
    def __init__(self, *, model: str, language="en", binary="whisper-cli",
                 sample_rate=WHISPER_RATE, threads=6, **kwargs):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._model, self._language, self._binary, self._threads = model, language, binary, threads

    def can_generate_metrics(self) -> bool:
        return False

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        audio = _to_16k(audio, self.sample_rate or WHISPER_RATE)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        try:
            with wave.open(tmp.name, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(WHISPER_RATE); w.writeframes(audio)
            proc = await asyncio.create_subprocess_exec(
                self._binary, "-m", self._model, "-f", tmp.name,
                "-l", self._language, "-nt", "-np", "-t", str(self._threads),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
        if proc.returncode != 0:
            logger.error(f"[whisper-cli] error: {err.decode(errors='ignore')[:200]}")
            return
        text = " ".join(out.decode(errors="ignore").split()).strip()
        if text:
            yield TranscriptionFrame(text, "user", time_now_iso8601())


async def make_stt(*, model: str, language: str, port: int, use_server: bool):
    """Cria o STT: whisper-server se der, senao whisper-cli."""
    if use_server:
        try:
            base = await ensure_server(model=model, port=port, language=language)
            return WhisperServerSTT(base_url=base, language=language)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"whisper-server unavailable ({e}); using whisper-cli")
    return WhisperCliSTT(model=model, language=language)
