"""Orchestrates one phone call: caller audio in, spoken reply out.

Key behaviour this class exists to demonstrate:
  1. Incremental synthesis — the first sentence of the reply is spoken while
     the LLM is still generating the rest of it, instead of waiting for the
     full response before any audio goes out.
  2. Barge-in — if the caller starts talking while the assistant is still
     speaking, playback is cancelled immediately instead of talking over them.

Deliberately transport-agnostic: it only talks to the CallTransport
interface, so it doesn't know or care whether the audio came from a real
phone call. Every turn is written to CallLog as it happens, which is what
the dashboard reads from.
"""
from __future__ import annotations

import asyncio
import logging
import time

from .call_log import CallLog
from .config import Settings
from .providers.llm import LLMProvider, sentence_chunks
from .providers.stt import DeepgramSTT
from .providers.telephony import CallTransport
from .providers.tts import ElevenLabsTTS
from .tools import TOOLS

logger = logging.getLogger("voxbridge.session")


class VoiceSession:
    def __init__(self, transport: CallTransport, settings: Settings, llm: LLMProvider, call_log: CallLog):
        self.transport = transport
        self.settings = settings
        self.llm = llm
        self.call_log = call_log
        self.stt = DeepgramSTT(
            api_key=settings.deepgram_api_key,
            model=settings.deepgram_model,
            sample_rate=transport.stt_sample_rate,
            encoding=transport.stt_encoding,
            endpointing_ms=settings.end_of_utterance_silence_ms,
        )
        self.tts = ElevenLabsTTS(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            output_format=transport.tts_output_format,
        )
        self.history: list[dict[str, str]] = []
        self._speaking_task: asyncio.Task | None = None
        self._assistant_speaking = False
        self._utterance_started_at: float = 0.0
        self._call_id: int = 0

    async def run(self) -> None:
        caller_number = await self.transport.caller_number()
        self._call_id = self.call_log.start_call(caller_number)
        await self.stt.connect()
        try:
            await asyncio.gather(self._read_caller_audio(), self._listen_transcripts())
        finally:
            if self._speaking_task and not self._speaking_task.done():
                self._speaking_task.cancel()
            await self.stt.close()
            self.call_log.end_call(self._call_id)

    async def _read_caller_audio(self) -> None:
        async for chunk in self.transport.audio_in():
            await self.stt.send_audio(chunk)

    async def _listen_transcripts(self) -> None:
        async for event in self.stt.events():
            if event.speech_started and self._assistant_speaking:
                await self._barge_in()
                continue
            if event.is_final and event.text:
                self._utterance_started_at = time.monotonic()
                await self._handle_utterance(event.text)

    async def _barge_in(self) -> None:
        logger.info("barge-in: caller interrupted the assistant")
        if self._speaking_task and not self._speaking_task.done():
            self._speaking_task.cancel()
        await self.transport.clear_playback()
        self._assistant_speaking = False

    async def _handle_utterance(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        self.call_log.log_turn(self._call_id, "caller", text)
        self._speaking_task = asyncio.create_task(self._respond())

    async def _respond(self) -> None:
        self._assistant_speaking = True
        first_audio_sent = False
        reply_parts: list[str] = []
        try:
            deltas = self.llm.stream_reply(self.history, self.settings.resolved_system_prompt(), TOOLS)
            async for sentence in sentence_chunks(deltas):
                reply_parts.append(sentence)

                async def _single(s: str = sentence):
                    yield s

                async for audio_chunk in self.tts.speak(_single()):
                    if not first_audio_sent:
                        latency_ms = (time.monotonic() - self._utterance_started_at) * 1000
                        logger.info("time-to-first-audio: %.0fms", latency_ms)
                        self.call_log.log_first_audio_latency(self._call_id, latency_ms)
                        first_audio_sent = True
                    await self.transport.audio_out(audio_chunk)
        except asyncio.CancelledError:
            logger.info("response cancelled mid-flight (barge-in)")
        finally:
            self._assistant_speaking = False
            if reply_parts:
                full_reply = " ".join(reply_parts)
                self.history.append({"role": "assistant", "content": full_reply})
                self.call_log.log_turn(self._call_id, "assistant", full_reply)
