# Voxbridge

A real-time voice agent that runs entirely in the browser: speak into your
mic, get a spoken reply back, and interrupt it mid-sentence like a real
phone call — no telephony number or SIP trunk required to try it.

## Why this exists

Most "AI agent" demos are request/response: send text, wait, get text back.
A phone call is a different engineering problem — audio has to be
transcribed, reasoned about, and spoken back **while the conversation is
still happening**, and a caller who starts talking over the assistant
expects it to shut up immediately, not finish its sentence. This project is
a from-scratch reference implementation of that pipeline, built to be read
and extended rather than just run as a black box.

## What it actually does

```
 mic (browser) --PCM16/16kHz--> WebSocket --> Deepgram (streaming STT)
                                                     |
                                          final transcript ready
                                                     v
                                            LLM (OpenAI or Anthropic)
                                          streamed token by token
                                                     v
                                   sentence boundary reached --> ElevenLabs (streaming TTS)
                                                     |
                                        audio bytes streamed back
                                                     v
                            WebSocket --> browser AudioContext --> speaker
```

Two things this pipeline is specifically built to demonstrate:

- **Incremental synthesis** — the first sentence of the reply is spoken
  while the LLM is still generating the rest of it (see
  `sentence_chunks()` in `backend/app/providers/llm.py`), instead of
  waiting for the full response before any audio goes out.
- **Barge-in** — Deepgram's `vad_events` tells the server the instant the
  caller starts speaking again. If the assistant is still talking, its
  in-flight LLM/TTS task is cancelled and the browser is told to stop
  playback immediately (`backend/app/session.py`, `_barge_in()`).

The server also logs a measured **time-to-first-audio** for every turn —
the metric that actually matters for how a voice agent *feels*, not just
whether it eventually answers correctly.

## Running it

Nothing in this repo works without your own API keys — none are bundled.

1. `cd backend && pip install -r requirements.txt`
2. `cp ../.env.example .env` and fill in your own keys:
   - [Deepgram](https://console.deepgram.com) for speech-to-text (free trial credit)
   - [ElevenLabs](https://elevenlabs.io) for text-to-speech (free tier available)
   - OpenAI or Anthropic for the LLM (set `LLM_PROVIDER` accordingly)
3. `uvicorn app.main:app --reload --app-dir backend`
4. Open `http://localhost:8000`, click **Start call**, and talk.

## Known limitations (by design, documented rather than hidden)

- The mic downsampler in `pcm-processor.js` is nearest-neighbour, not a
  proper band-limited resampler — fine for speech recognition, not
  audiophile-grade.
- This is a browser demo, not a phone line. Extending it to real calls
  means swapping the browser WebSocket for Twilio Media Streams (or a SIP
  trunk via LiveKit) feeding the same `VoiceSession` — the STT/LLM/TTS
  pipeline in `backend/app/` doesn't change, only the audio transport does.
- Conversation memory lives only for the duration of one call; there's no
  cross-session persistence.

## License

MIT — see [LICENSE](LICENSE).
