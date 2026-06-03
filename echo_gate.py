"""EchoGate — anti-eco half-duplex, sem fone e sem dependencia comercial.

Sem fone, o mic capta a propria voz do agente e ele se responde num loop. Filtros de
ruido (rnnoise/krisp) NAO resolvem: fala limpa nao e ruido. A solucao confiavel sem
hardware/licenca e half-duplex: enquanto o agente FALA, o mic e silenciado (descarta o
audio de entrada antes do VAD). Trade-off: nao da pra interromper a fala dele sem fone
(com fone, CALL_ECHO_GATE=0 traz o barge-in de volta).

Posicao no pipeline: logo depois de transport.input(), antes do VAD.
"""
import time

from pipecat.frames.frames import (
    BotStartedSpeakingFrame, BotStoppedSpeakingFrame, Frame, InputAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection


class EchoGate(FrameProcessor):
    def __init__(self, *, tail_secs: float = 0.4):
        super().__init__()
        self._tail = tail_secs
        self._bot_speaking = False
        self._unmute_at = 0.0

    def _muted(self) -> bool:
        return self._bot_speaking or time.monotonic() < self._unmute_at

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            self._unmute_at = time.monotonic() + self._tail
        if isinstance(frame, InputAudioRawFrame) and self._muted():
            return
        await self.push_frame(frame, direction)
