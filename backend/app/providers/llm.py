"""Pluggable streaming LLM provider.

Only "openai" and "anthropic" are wired in, but adding a third backend
just means implementing the LLMProvider interface below.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import AsyncIterator

Message = dict[str, str]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


class LLMProvider(ABC):
    @abstractmethod
    async def stream_reply(self, history: list[Message], system_prompt: str) -> AsyncIterator[str]:
        """Yield raw text deltas as the model generates them."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def stream_reply(self, history: list[Message], system_prompt: str) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system_prompt}, *history],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def stream_reply(self, history: list[Message], system_prompt: str) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=300,
            system=system_prompt,
            messages=history,
        ) as stream:
            async for text in stream.text_stream:
                yield text


def build_llm_provider(provider: str, *, openai_api_key: str, openai_model: str,
                        anthropic_api_key: str, anthropic_model: str) -> LLMProvider:
    if provider == "openai":
        return OpenAIProvider(openai_api_key, openai_model)
    if provider == "anthropic":
        return AnthropicProvider(anthropic_api_key, anthropic_model)
    raise ValueError(f"Unknown LLM_PROVIDER '{provider}'. Expected 'openai' or 'anthropic'.")


async def sentence_chunks(deltas: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffers raw text deltas and yields complete sentences as soon as they're ready.

    This is what lets TTS start speaking the first sentence while the LLM is
    still generating the rest of the reply, instead of waiting for the full
    response before any audio goes out.
    """
    buffer = ""
    async for delta in deltas:
        buffer += delta
        parts = _SENTENCE_END.split(buffer)
        if len(parts) > 1:
            for sentence in parts[:-1]:
                sentence = sentence.strip()
                if sentence:
                    yield sentence
            buffer = parts[-1]
    if buffer.strip():
        yield buffer.strip()
