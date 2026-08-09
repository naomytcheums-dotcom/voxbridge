"""Pluggable streaming LLM provider with tool-calling support.

Only "openai" and "anthropic" are wired in, but adding a third backend just
means implementing the LLMProvider interface below.

Tool-calling loop: each provider streams a turn; if the model asks to call
tools, they're executed via `tools.dispatch()` and the results are fed back
for another turn (up to MAX_TOOL_HOPS). The turn that produces plain text
instead of tool calls is streamed live, sentence by sentence, straight to
the caller — that's the one that actually gets spoken.
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from ..tools import dispatch

Message = dict[str, Any]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MAX_TOOL_HOPS = 4


class LLMProvider(ABC):
    @abstractmethod
    async def stream_reply(
        self, history: list[Message], system_prompt: str, tools: list[dict] | None = None
    ) -> AsyncIterator[str]:
        """Yield raw text deltas for the final, spoken reply.

        Tool calls the model makes along the way are executed and fed back
        internally — callers only ever see the text that should be spoken.
        """
        raise NotImplementedError


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]},
    }


def _to_anthropic_tool(tool: dict) -> dict:
    return {"name": tool["name"], "description": tool["description"], "input_schema": tool["parameters"]}


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def stream_reply(
        self, history: list[Message], system_prompt: str, tools: list[dict] | None = None
    ) -> AsyncIterator[str]:
        messages: list[Message] = [{"role": "system", "content": system_prompt}, *history]
        openai_tools = [_to_openai_tool(t) for t in tools] if tools else None

        for _ in range(MAX_TOOL_HOPS):
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=openai_tools,
                stream=True,
            )

            text_parts: list[str] = []
            pending_calls: dict[int, dict[str, str]] = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    text_parts.append(delta.content)
                    yield delta.content
                for tc in delta.tool_calls or []:
                    entry = pending_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

            if not pending_calls:
                return  # plain text reply already streamed above — done

            ordered = [pending_calls[i] for i in sorted(pending_calls)]
            messages.append({
                "role": "assistant",
                "content": "".join(text_parts) or None,
                "tool_calls": [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in ordered
                ],
            })
            for c in ordered:
                args = json.loads(c["arguments"] or "{}")
                result = dispatch(c["name"], args)
                messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)})


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model

    async def stream_reply(
        self, history: list[Message], system_prompt: str, tools: list[dict] | None = None
    ) -> AsyncIterator[str]:
        messages: list[Message] = list(history)
        anthropic_tools = [_to_anthropic_tool(t) for t in tools] if tools else None

        for _ in range(MAX_TOOL_HOPS):
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=400,
                system=system_prompt,
                messages=messages,
                tools=anthropic_tools,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()

            tool_uses = [block for block in final.content if block.type == "tool_use"]
            if not tool_uses:
                return  # plain text reply already streamed above — done

            messages.append({"role": "assistant", "content": final.content})
            tool_results = []
            for block in tool_uses:
                result = dispatch(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
            messages.append({"role": "user", "content": tool_results})


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
