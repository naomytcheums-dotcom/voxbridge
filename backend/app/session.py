"""Orchestrates one voice call: mic audio in, spoken reply out.

Key behaviour this class exists to demonstrate:
  1. Incremental synthesis — the first sentence of the reply is spoken while
     the LLM is still generating the rest of it, instead of waiting for the
     full response before any audio goes out.
  2. Barge-in — if the caller starts talking while the assistant is still
     speaking, playback is cancelled immediately instead of talking over them.
"""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import WebSocket, WebSocketDisconnect

from .config import Settings
from .providers.llm import LLMProvider, sentence_chunks
from .providers.stt import DeepgramSTT
from .providers.tts import ElevenLabsTTS
from .tools import TOOLS

logger = logging.getLogger("voxbridge.session")


class VoiceSession:
    def __init__(self, websocket: WebSocket, settings: Settings, llm: LLMProvider):
        self.ws = websocket
        self.settings = settings
        self.llm = llm
        self.stt = DeepgramSTT(
            api_key=settings.deepgram_api_key,
            model=settings.deepgram_model,
            endpointing_ms=settings.end_of_utterance_silence_ms,
        )
        self.tts = ElevenLabsTTS(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )
        self.history: list[dict[str, str]] = []
        self._speaking_task: asyncio.Task | None = None
        self._assistant_speaking = False
        self._utterance_started_at: float = 0.0

    async def run(self) -> None:
        await self.stt.connect()
        try:
            await asyncio.gather(self._read_client_audio(), self._listen_transcripts())
        except WebSocketDisconnect:
            logger.info("client disconnected")
        finally:
            if self._speaking_task and not self._speaking_task.done():
                self._speaking_task.cancel()
            await self.stt.close()

    async def _read_client_audio(self) -> None:
        while True:
            message = await self.ws.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect()
            audio = message.get("bytes")
            if audio:
                await self.stt.send_audio(audio)

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
        await self.ws.send_json({"type": "stop_audio"})
        self._assistant_speaking = False

    async def _handle_utterance(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        await self.ws.send_json({"type": "transcript", "text": text})
        self._speaking_task = asyncio.create_task(self._respond())

    async def _respond(self) -> None:
        self._assistant_speaking = True
        first_audio_sent = False
        reply_parts: list[str] = []
        try:
            deltas = self.llm.stream_reply(self.history, self.settings.resolved_system_prompt(), TOOLS)
            async for sentence in sentence_chunks(deltas):
                reply_parts.append(sentence)
                await self.ws.send_json({"type": "assistant_text", "text": sentence})

                async def _single(s: str = sentence):
                    yield s

                async for audio_chunk in self.tts.speak(_single()):
                    if not first_audio_sent:
                        latency_ms = (time.monotonic() - self._utterance_started_at) * 1000
                        logger.info("time-to-first-audio: %.0fms", latency_ms)
                        first_audio_sent = True
                    await self.ws.send_bytes(audio_chunk)
        except asyncio.CancelledError:
            logger.info("response cancelled mid-flight (barge-in)")
        finally:
            self._assistant_speaking = False
            await self.ws.send_json({"type": "assistant_done"})
            if reply_parts:
                self.history.append({"role": "assistant", "content": " ".join(reply_parts)})
