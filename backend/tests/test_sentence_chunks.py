import pytest

from app.providers.llm import sentence_chunks


async def _deltas(*pieces: str):
    for piece in pieces:
        yield piece


@pytest.mark.asyncio
async def test_splits_multiple_sentences_delivered_in_one_delta():
    out = [s async for s in sentence_chunks(_deltas("Hi there. How can I help you today?"))]
    assert out == ["Hi there.", "How can I help you today?"]


@pytest.mark.asyncio
async def test_sentence_split_across_many_small_deltas():
    pieces = list("Hello there. Welcome!")  # one delta per character, worst case
    out = [s async for s in sentence_chunks(_deltas(*pieces))]
    assert out == ["Hello there.", "Welcome!"]


@pytest.mark.asyncio
async def test_trailing_text_without_punctuation_is_still_flushed():
    out = [s async for s in sentence_chunks(_deltas("We have that in stock"))]
    assert out == ["We have that in stock"]


@pytest.mark.asyncio
async def test_empty_stream_yields_nothing():
    out = [s async for s in sentence_chunks(_deltas())]
    assert out == []
