"""Streaming text-to-speech provider (ElevenLabs real-time API).

Protocol reference: https://elevenlabs.io/docs/api-reference/websockets
Yields raw audio bytes (mp3) as they arrive, so playback can start on the
first chunk instead of waiting for the whole sentence to be synthesized.
"""
from __future__ import annotations

import base64
import json
from typing import AsyncIterator

import websockets

ELEVENLABS_WS_URL = "wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"


class ElevenLabsTTS:
    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_turbo_v2"):
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id

    async def speak(self, text_chunks: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Streams `text_chunks` (e.g. one sentence at a time) in and audio bytes out."""
        url = f"{ELEVENLABS_WS_URL.format(voice_id=self._voice_id)}?model_id={self._model_id}"
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({
                "text": " ",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                "xi_api_key": self._api_key,
            }))

            async def _sender():
                async for chunk in text_chunks:
                    await ws.send(json.dumps({"text": chunk + " "}))
                await ws.send(json.dumps({"text": ""}))  # signal end of input

            import asyncio
            sender_task = asyncio.create_task(_sender())

            try:
                async for raw in ws:
                    data = json.loads(raw)
                    audio_b64 = data.get("audio")
                    if audio_b64:
                        yield base64.b64decode(audio_b64)
                    if data.get("isFinal"):
                        break
            finally:
                sender_task.cancel()
