import logging
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles

from .call_log import CallLog
from .config import get_settings
from .providers.llm import build_llm_provider
from .providers.telephony import build_call_control, build_transport
from .session import VoiceSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("voxbridge.main")

app = FastAPI(title="Voxbridge")
settings = get_settings()
call_log = CallLog(settings.call_log_db_path)


def _stream_url() -> str:
    """Turns the configured public https URL into the wss:// URL the carrier streams audio to."""
    base = settings.telephony_public_url.rstrip("/")
    host = base.split("://", 1)[-1]
    return f"wss://{host}/telephony/stream"


@app.post("/telephony/webhook")
async def telephony_webhook(request: Request) -> dict:
    """Receives call lifecycle events from the telephony carrier and drives the call."""
    body = await request.json()
    event_type = body.get("data", {}).get("event_type")
    call_control_id = body.get("data", {}).get("payload", {}).get("call_control_id")

    if not call_control_id:
        return {"ok": True}

    call_control = build_call_control(settings.telephony_provider, settings.telephony_api_key, _stream_url())

    if event_type == "call.initiated":
        await call_control.answer(call_control_id)
    elif event_type == "call.answered":
        await call_control.start_streaming(call_control_id)

    return {"ok": True}


@app.websocket("/telephony/stream")
async def telephony_stream(websocket: WebSocket) -> None:
    """Carries call audio for the duration of one phone call."""
    await websocket.accept()
    transport = build_transport(settings.telephony_provider, websocket)
    await transport.wait_for_start()

    llm = build_llm_provider(
        settings.llm_provider,
        openai_api_key=settings.openai_api_key,
        openai_model=settings.openai_model,
        anthropic_api_key=settings.anthropic_api_key,
        anthropic_model=settings.anthropic_model,
    )
    session = VoiceSession(transport, settings, llm, call_log)
    await session.run()


@app.get("/api/calls")
def api_list_calls() -> list[dict]:
    return call_log.list_calls()


@app.get("/api/calls/{call_id}")
def api_get_call(call_id: int) -> dict | None:
    return call_log.get_call(call_id)


@app.get("/api/stats")
def api_stats() -> dict:
    return call_log.latency_stats()


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="dashboard")
