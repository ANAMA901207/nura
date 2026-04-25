"""
bot/main.py
===========
Aplicación FastAPI que expone el webhook de Telegram para el bot de Nura.

Endpoints
---------
GET  /health   → {"status": "ok"}  (healthcheck para Railway/uptime monitors)
POST /webhook  → retorna {"ok": True} en < 2 s y procesa en background

Flujo del webhook (fix anti-loop, Sprint 25)
---------------------------------------------
Telegram reenvía el mismo update si no recibe respuesta en ~30 s.
Para evitar el loop cuando Gemini tarda 30-60 s:

1. /webhook parsea el JSON del update.
2. Lanza asyncio.create_task(_process_and_send(token, update)).
3. Retorna JSONResponse({"ok": True}) INMEDIATAMENTE (< 2 s).
4. La tarea de fondo ejecuta process_update (async), que a su vez
   llama a handle_capturar / handle_free_message usando asyncio.to_thread
   para no bloquear el event loop mientras Gemini responde.
5. Cuando termina, _send_message envía la respuesta al usuario.

Startup
-------
Al arrancar, registra el webhook con la API de Telegram usando:
  - TELEGRAM_TOKEN  : token del bot (BotFather).
  - WEBHOOK_URL     : URL pública donde Telegram enviará los updates.

Si TELEGRAM_TOKEN o WEBHOOK_URL no están definidas, la app arranca igual
pero no registra el webhook (útil para tests locales y CI).
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

# Asegurar que los módulos de Nura sean importables desde cualquier cwd.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

from bot.handlers import process_update
from bot.scheduler import run_scheduler

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
    """Gestiona el ciclo de vida de la app: registra webhook y lanza scheduler."""
    await _register_webhook()
    asyncio.create_task(run_scheduler())
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Nura Bot", version="1.0.0", lifespan=_lifespan)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    """Healthcheck — siempre retorna 200 {"status": "ok"}."""
    return JSONResponse({"status": "ok"})


@app.post("/webhook")
async def webhook(request: Request) -> JSONResponse:
    """
    Recibe un update de Telegram y retorna {"ok": True} inmediatamente.

    El procesamiento real (que puede tardar 30-60 s si invoca Gemini) se
    ejecuta en una tarea de fondo con asyncio.create_task().  Así Telegram
    recibe el 200 en < 2 s y no reenvía el update.
    """
    try:
        update = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    token = os.environ.get("TELEGRAM_TOKEN", "")
    asyncio.create_task(_process_and_send(token, update))

    return JSONResponse({"ok": True})


# ── Background task ───────────────────────────────────────────────────────────

async def _process_and_send(token: str, update: dict) -> None:
    """
    Tarea de fondo: procesa el update y envía la respuesta a Telegram.

    Llama a process_update (async) que internamente usa asyncio.to_thread
    para los handlers lentos (Gemini), manteniendo el event loop libre.

    Si el resultado tiene type='voice' → usa sendVoice (OGG/OPUS).
    Si no → usa sendMessage como siempre.
    Los errores se registran en consola sin propagar excepciones.
    """
    try:
        result = await process_update(update)
        if not (result.get("handled") and result.get("chat_id") and token):
            return

        chat_id = result["chat_id"]

        if result.get("type") == "voice" and result.get("audio_bytes"):
            await _send_voice(token, chat_id, result["audio_bytes"])
        elif result.get("text"):
            await _send_message(token, chat_id, result["text"])
    except Exception as exc:
        print(f"[NuraBot] Error en background task: {exc}")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _send_voice(token: str, chat_id: int, audio_bytes: bytes) -> None:
    """
    Envía una nota de voz OGG/OPUS a un chat de Telegram usando sendVoice.

    Telegram reproduce OGG/OPUS nativamente sin que el usuario tenga que
    descargar el archivo.  Los errores se registran en consola.
    """
    url = _TELEGRAM_API.format(token=token, method="sendVoice")
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                url,
                data={"chat_id": str(chat_id)},
                files={"voice": ("voice.ogg", audio_bytes, "audio/ogg")},
                timeout=60,
            )
    except Exception as exc:
        print(f"[NuraBot] Error al enviar voz a {chat_id}: {exc}")


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
            await client.post(url, json=payload, timeout=30)
    except Exception as exc:
        print(f"[NuraBot] Error al enviar mensaje a {chat_id}: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "bot.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
