"""Reproducible latency benchmark — no phone call needed.

Runs a fixed set of realistic caller utterances straight through the real
LLM + TTS pipeline (the same code session.py drives a live call with) and
reports time-to-first-audio, split by whether the turn needed a tool call.
That split matters: a tool call means a full extra LLM round-trip before
any audio can start, so it should — and does — cost more.

Requires real API keys in `.env` (LLM + ElevenLabs). Doesn't touch the
telephony or STT layer, so it runs identically whether or not a phone
number is wired up yet.

Usage:
    cd backend && python benchmark.py [--runs 5]
"""
from __future__ import annotations

import argparse
import asyncio
import time

from app.config import get_settings
from app.providers.llm import build_llm_provider, sentence_chunks
from app.providers.tts import ElevenLabsTTS
from app.tools import TOOLS

SCENARIOS = [
    {"label": "no_tool_smalltalk", "text": "Hi, are you open on Sundays?"},
    {"label": "no_tool_farewell", "text": "Okay, thanks, bye!"},
    {"label": "tool_search_product", "text": "Do you have any red bags?"},
    {"label": "tool_check_stock", "text": "How many black sneakers do you have left?"},
]


async def time_one_turn(settings, scenario: dict) -> dict:
    llm = build_llm_provider(
        settings.llm_provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
    )
    tts = ElevenLabsTTS(
        api_key=settings.elevenlabs_api_key,
        voice_id=settings.elevenlabs_voice_id,
        output_format="mp3_44100_128",
    )

    history = [{"role": "user", "content": scenario["text"]}]
    started = time.monotonic()
    first_audio_ms = None

    async for sentence in sentence_chunks(llm.stream_reply(history, settings.resolved_system_prompt(), TOOLS)):
        async def _single(s=sentence):
            yield s

        async for _chunk in tts.speak(_single()):
            if first_audio_ms is None:
                first_audio_ms = (time.monotonic() - started) * 1000
            break  # only need the first chunk's timing for this sentence
        break  # only the first spoken sentence matters for time-to-first-audio

    return {"label": scenario["label"], "text": scenario["text"], "first_audio_ms": first_audio_ms}


def _percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = min(len(ordered) - 1, int(round(p * (len(ordered) - 1))))
    return ordered[idx]


async def main(runs: int) -> None:
    settings = get_settings()
    results = []

    for i in range(runs):
        for scenario in SCENARIOS:
            result = await time_one_turn(settings, scenario)
            results.append(result)
            print(f"run {i + 1}/{runs} · {result['label']:<22} · {result['first_audio_ms']:.0f}ms")

    print("\n--- summary (time-to-first-audio) ---")
    by_label: dict[str, list[float]] = {}
    for r in results:
        by_label.setdefault(r["label"], []).append(r["first_audio_ms"])

    for label, values in by_label.items():
        print(f"{label:<22} p50={_percentile(values, 0.5):>6.0f}ms  p95={_percentile(values, 0.95):>6.0f}ms  n={len(values)}")

    no_tool = [v for r in results for v in [r["first_audio_ms"]] if "no_tool" in r["label"]]
    with_tool = [v for r in results for v in [r["first_audio_ms"]] if r["label"].startswith("tool_")]
    if no_tool and with_tool:
        print(f"\ntool-call overhead: +{(sum(with_tool) / len(with_tool)) - (sum(no_tool) / len(no_tool)):.0f}ms on average")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    asyncio.run(main(args.runs))
