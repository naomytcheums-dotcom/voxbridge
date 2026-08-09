"""Streaming speech-to-text provider (Deepgram real-time API).

Protocol reference: https://developers.deepgram.com/docs/streaming
Audio format expected by this client: 16-bit PCM, mono, 16kHz.
"""
from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import AsyncIterator

import websockets

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


@dataclass
class TranscriptEvent:
    text: str
    is_final: bool
    speech_started: bool = False


class DeepgramSTT:
    """Wraps a single Deepgram streaming session for one voice call."""

    def __init__(self, api_key: str, model: str, sample_rate: int = 16000, endpointing_ms: int = 700):
        self._api_key = api_key
        self._model = model
        self._sample_rate = sample_rate
        self._endpointing_ms = endpointing_ms
        self._ws: websockets.WebSocketClientProtocol | None = None

    async def connect(self) -> None:
        params = (
            f"model={self._model}"
            f"&encoding=linear16"
            f"&sample_rate={self._sample_rate}"
            f"&channels=1"
            f"&interim_results=true"
            f"&punctuate=true"
            f"&endpointing={self._endpointing_ms}"
            f"&vad_events=true"
        )
        self._ws = await websockets.connect(
            f"{DEEPGRAM_WS_URL}?{params}",
            additional_headers={"Authorization": f"Token {self._api_key}"},
            ping_interval=5,
        )

    async def send_audio(self, chunk: bytes) -> None:
        if self._ws is None:
            raise RuntimeError("DeepgramSTT.connect() must be called before send_audio()")
        await self._ws.send(chunk)

    async def close(self) -> None:
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.send(json.dumps({"type": "CloseStream"}))
            await self._ws.close()
            self._ws = None

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        """Yields transcript events as Deepgram streams them back."""
        if self._ws is None:
            raise RuntimeError("DeepgramSTT.connect() must be called before events()")
        async for raw in self._ws:
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "SpeechStarted":
                yield TranscriptEvent(text="", is_final=False, speech_started=True)
                continue

            if msg_type == "Results":
                alt = data.get("channel", {}).get("alternatives", [{}])[0]
                text = alt.get("transcript", "")
                if not text:
                    continue
                yield TranscriptEvent(text=text, is_final=bool(data.get("is_final")))
