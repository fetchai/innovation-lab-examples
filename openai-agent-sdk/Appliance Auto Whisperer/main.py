"""HTTP entrypoint for Appliance Auto Whisperer."""

from fastapi import FastAPI

from app.chat.protocol_handler import ProtocolHandler
from app.config.logging_config import configure_logging
from app.config.settings import get_settings
from app.observability.health import health_payload

configure_logging()
settings = get_settings()
app = FastAPI(title="Appliance Auto Whisperer", version="0.2.0")
_handler = ProtocolHandler()


@app.get("/health")
def health() -> dict:
    return health_payload()


@app.get("/healthz")
def healthz() -> dict:
    return health_payload()


@app.post("/v1/chat")
async def chat(payload: dict) -> dict:
    return await _handler.handle(payload)
