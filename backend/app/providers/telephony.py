"""Telephony transport — bridges a real phone call to the same STT/LLM/TTS
pipeline the rest of this app uses.

Two moving pieces make a real call work:
  1. A Call Control webhook (`/telephony/webhook`) that answers an incoming
     call and tells the carrier to start streaming its audio to us.
  2. A Media Streaming WebSocket (`/telephony/stream`) that carries the
     actual audio, both directions, for the duration of the call.

Only one carrier is implemented below, but nothing outside this module
knows which one — see `CallTransport` and `build_transport()`. Swapping
carriers later means adding one more class here, not touching session.py.

Known gap: the exact Media Streaming message shape (field names, event
names) is implemented to the best of current documented knowledge and
should be re-verified against the carrier's live docs before a first real
call — these details do shift between API versions.
"""
from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx
from fastapi import WebSocket

logger = logging.getLogger("voxbridge.telephony")


class CallTransport(ABC):
    """What VoiceSession needs from a phone call, regardless of carrier."""

    stt_encoding: str
    stt_sample_rate: int
    tts_output_format: str

    @abstractmethod
    async def wait_for_start(self) -> None:
        """Consumes the carrier's connection handshake before audio starts flowing."""

    @abstractmethod
    async def audio_in(self) -> AsyncIterator[bytes]:
        """Yields raw caller audio chunks, already in this transport's STT encoding."""

    @abstractmethod
    async def audio_out(self, chunk: bytes) -> None:
        """Sends one chunk of synthesized speech back to the caller."""

    @abstractmethod
    async def clear_playback(self) -> None:
        """Barge-in: stop whatever audio is currently queued on the line."""

    async def caller_number(self) -> str | None:
        return None


class TelnyxTransport(CallTransport):
    stt_encoding = "mulaw"
    stt_sample_rate = 8000
    tts_output_format = "ulaw_8000"

    def __init__(self, websocket: WebSocket):
        self._ws = websocket
        self._stream_id: str | None = None
        self._caller_number: str | None = None

    async def wait_for_start(self) -> None:
        while True:
            raw = await self._ws.receive_text()
            data = json.loads(raw)
            if data.get("event") == "start":
                start = data.get("start", {})
                self._stream_id = data.get("stream_id") or start.get("stream_id")
                self._caller_number = start.get("from")
                return

    async def caller_number(self) -> str | None:
        return self._caller_number

    async def audio_in(self) -> AsyncIterator[bytes]:
        while True:
            raw = await self._ws.receive_text()
            data = json.loads(raw)
            event = data.get("event")
            if event == "media":
                payload = data.get("media", {}).get("payload")
                if payload:
                    yield base64.b64decode(payload)
            elif event == "stop":
                return

    async def audio_out(self, chunk: bytes) -> None:
        await self._ws.send_text(json.dumps({
            "event": "media",
            "stream_id": self._stream_id,
            "media": {"payload": base64.b64encode(chunk).decode("ascii")},
        }))

    async def clear_playback(self) -> None:
        await self._ws.send_text(json.dumps({"event": "clear", "stream_id": self._stream_id}))


class TelephonyCallControl(ABC):
    """REST calls that drive the call itself (answer it, start streaming its audio)."""

    @abstractmethod
    async def answer(self, call_control_id: str) -> None: ...

    @abstractmethod
    async def start_streaming(self, call_control_id: str) -> None: ...


class TelnyxCallControl(TelephonyCallControl):
    BASE_URL = "https://api.telnyx.com/v2"

    def __init__(self, api_key: str, stream_url: str):
        self._api_key = api_key
        self._stream_url = stream_url

    async def answer(self, call_control_id: str) -> None:
        await self._post(f"/calls/{call_control_id}/actions/answer", {})

    async def start_streaming(self, call_control_id: str) -> None:
        await self._post(
            f"/calls/{call_control_id}/actions/streaming_start",
            {"stream_url": self._stream_url, "stream_track": "both_tracks"},
        )

    async def _post(self, path: str, body: dict) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.BASE_URL}{path}",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=body,
            )
            if resp.status_code >= 300:
                logger.error("telephony call-control error %s: %s", resp.status_code, resp.text)


def build_transport(provider: str, websocket: WebSocket) -> CallTransport:
    if provider == "telnyx":
        return TelnyxTransport(websocket)
    raise ValueError(f"Unknown TELEPHONY_PROVIDER '{provider}'")


def build_call_control(provider: str, api_key: str, stream_url: str) -> TelephonyCallControl:
    if provider == "telnyx":
        return TelnyxCallControl(api_key, stream_url)
    raise ValueError(f"Unknown TELEPHONY_PROVIDER '{provider}'")
