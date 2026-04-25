"""
bot/scheduler.py
================
Scheduler de recordatorios diarios de Nura.

Corre dentro del mismo proceso FastAPI como tarea asyncio en background.
Cada 60 segundos verifica qué usuarios deben recibir un recordatorio y
les envía un mensaje por Telegram con su progreso del día.

Condiciones para enviar un recordatorio
----------------------------------------
- El usuario tiene telegram_id vinculado.
- Su reminder_time coincide con la hora actual (HH:MM).
- El número de conceptos capturados hoy es menor que su daily_goal.

Formato del mensaje
--------------------
  🌙 Hey [nombre], hoy llevas X de Y conceptos.
  Tienes Z pendientes de repasar.
  ¿Le dedicamos 5 minutos?
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from db.operations import get_users_to_remind, get_today_count
from bot.nura_bridge import get_pending_concepts

_TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _build_reminder_message(username: str, today_count: int, daily_goal: int, pending: int) -> str:
    """
    Construye el mensaje de recordatorio para el usuario.

    Parámetros
    ----------
    username    : Nombre de usuario en Nura.
    today_count : Conceptos capturados hoy.
    daily_goal  : Meta diaria del usuario.
    pending     : Conceptos pendientes de repasar (SM-2).

    Devuelve
    --------
    str — texto listo para enviar a Telegram.
    """
    return (
        f"🌙 Hey {username}, hoy llevas {today_count} de {daily_goal} conceptos.\n"
        f"Tienes {pending} pendientes de repasar.\n"
        f"¿Le dedicamos 5 minutos?"
    )


async def _send_reminder(token: str, telegram_id: str, text: str) -> None:
    """
    Envía el mensaje de recordatorio a un chat de Telegram.

    Los errores de envío se registran en consola pero no propagan excepciones
    para que el loop continúe con los demás usuarios.
    """
    url = _TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id": telegram_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=15)
            if not resp.json().get("ok"):
                print(f"[Scheduler] Telegram rechazó mensaje a {telegram_id}: {resp.text}")
    except Exception as exc:
        print(f"[Scheduler] Error al enviar recordatorio a {telegram_id}: {exc}")


async def run_scheduler() -> None:
    """
    Loop infinito que verifica cada 60 segundos si algún usuario
    debe recibir un recordatorio diario y lo envía por Telegram.
    """
    token = os.environ.get("TELEGRAM_TOKEN", "")
    if not token:
        print("[Scheduler] TELEGRAM_TOKEN no definido — scheduler inactivo.")
        return

    print("[Scheduler] Iniciado. Verificando recordatorios cada 60 s.")

    while True:
        try:
            current_time = datetime.now().strftime("%H:%M")
            users = await asyncio.to_thread(get_users_to_remind, current_time)

            for user in users:
                try:
                    today_count = await asyncio.to_thread(get_today_count, user.id)
                    if today_count >= user.daily_goal:
                        continue
                    pending_list = await asyncio.to_thread(get_pending_concepts, user.id)
                    pending = len(pending_list)
                    msg = _build_reminder_message(
                        user.username, today_count, user.daily_goal, pending
                    )
                    await _send_reminder(token, str(user.telegram_id), msg)
                    print(f"[Scheduler] Recordatorio enviado a {user.username} ({user.telegram_id})")
                except Exception as exc:
                    print(f"[Scheduler] Error procesando usuario {user.id}: {exc}")

        except Exception as exc:
            print(f"[Scheduler] Error en el loop principal: {exc}")

        await asyncio.sleep(60)
