"""
bot/main.py
===========
Aplicación FastAPI que expone el webhook de Telegram para el bot de Nura.

Endpoints
---------
GET  /health   → {"status": "ok"}  (healthcheck para Railway/uptime monitors)
POST /webhook  → recibe updates de Telegram y los despacha a handlers.process_update()

Startup
-------
Al arrancar, registra el webhook con la API de Telegram usando:
  - TELEGRAM_TOKEN  : token del bot (BotFather).
  - WEBHOOK_URL     : URL pública donde Telegram enviará los updates.

Ambas variables se leen del entorno (cargado desde .env con python-dotenv).

Si TELEGRAM_TOKEN o WEBHOOK_URL no están definidas, la app arranca igual
pero no registra el webhook (útil para tests locales y CI).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# Asegurar que los módulos de Nura sean importables desde cualquier cwd.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from bot.handlers import process_update

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def _register_webhook() -> None:
    """
    Registra el webhook con Telegram al arrancar la aplicación.

    Si TELEGRAM_TOKEN o WEBHOOK_URL no están definidas, no hace nada
    (permite arrancar el servidor en entornos de test sin credenciales).
    """
    token       = os.environ.get("TELEGRAM_TOKEN", "")
    webhook_url = os.environ.get("WEBHOOK_URL", "")

    if not token or not webhook_url:
        print("[NuraBot] TELEGRAM_TOKEN o WEBHOOK_URL no definidos — webhook no registrado.")
        return

    url = _TELEGRAM_API.format(token=token, method="setWebhook")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={"url": webhook_url}, timeout=10)
            data = resp.json()
            if data.get("ok"):
                print(f"[NuraBot] Webhook registrado en {webhook_url}")
            else:
                print(f"[NuraBot] Error al registrar webhook: {data}")
    except Exception as exc:
        print(f"[NuraBot] No se pudo registrar el webhook: {exc}")


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Gestiona el ciclo de vida de la app: registra webhook al arrancar."""
    await _register_webhook()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Nura Bot", version="1.0.0", lifespan=_lifespan)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    """Healthcheck — siempre retorna 200 {"status": "ok"}."""
    return JSONResponse({"status": "ok"})


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """
    Recibe un update de Telegram (JSON), lo procesa y envía la respuesta.

    Telegram espera siempre un 200 OK aunque no se envíe respuesta, para
    no reintentar el mismo update indefinidamente.
    """
    token = os.environ.get("TELEGRAM_TOKEN", "")

    try:
        update = await request.json()
    except Exception:
        return Response(status_code=200)

    result = process_update(update)

    if result.get("handled") and result.get("chat_id") and token:
        await _send_message(token, result["chat_id"], result["text"])

    return Response(status_code=200)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_message(token: str, chat_id: int, text: str) -> None:
    """
    Envía un mensaje de texto a un chat de Telegram.

    Usa parse_mode='Markdown' para soportar *negrita*, _cursiva_ y `código`.
    Los errores de envío se registran en consola pero no propagan excepciones
    (Telegram ya habrá recibido el 200 OK).
    """
    url = _TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id":    chat_id,
        "text":       text[:4096],   # límite de Telegram
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception as exc:
        print(f"[NuraBot] Error al enviar mensaje a {chat_id}: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot.main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
