"""
bot/handlers.py
===============
Lógica de negocio de cada comando del bot de Nura en Telegram.

Diseño async (Sprint 25 fix)
-----------------------------
- `process_update`, `handle_capturar` y `handle_free_message` son `async`
  para que puedan usar `asyncio.to_thread(run_tutor, ...)` y nunca bloquear
  el event loop de FastAPI mientras Gemini genera la respuesta.
- Los handlers rápidos (streak, meta, repasar, start, vincular) siguen siendo
  síncronos: no llaman a la IA y terminan en milisegundos.
- `main.py` llama a `process_update` desde una tarea de fondo
  (`asyncio.create_task`) para que `/webhook` retorne < 2 s.
- Los tests unitarios envuelven las llamadas async con `asyncio.run()`.
"""

from __future__ import annotations

import asyncio
from typing import Any


# ── Router principal (async) ──────────────────────────────────────────────────

async def process_update(update: dict) -> dict:
    """
    Router async que procesa un update de Telegram y devuelve la respuesta.

    Lee el mensaje del update, detecta si es un comando (empieza con '/')
    y delega a la función handler correspondiente.  Los handlers que invocan
    la IA son awaited; los rápidos se llaman directamente.

    Parámetros
    ----------
    update : dict con la estructura de un Update de Telegram.

    Devuelve
    --------
    dict con claves:
        chat_id  (int)  — destinatario de la respuesta.
        text     (str)  — texto de la respuesta.
        handled  (bool) — True si se procesó correctamente.
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"chat_id": None, "text": "", "handled": False}

    chat_id     = message.get("chat", {}).get("id")
    from_user   = message.get("from", {})
    telegram_id = from_user.get("id")
    username    = from_user.get("username", "")
    text        = (message.get("text") or "").strip()

    if not text or telegram_id is None:
        return {"chat_id": chat_id, "text": "", "handled": False}

    # ── Despacho por comando ──────────────────────────────────────────────────
    if text.startswith("/start"):
        response = handle_start(telegram_id, username)

    elif text.startswith("/capturar"):
        term = text[len("/capturar"):].strip()
        response = await handle_capturar(telegram_id, term)      # async: llama IA

    elif text.startswith("/repasar"):
        response = handle_repasar(telegram_id)

    elif text.startswith("/streak"):
        response = handle_streak(telegram_id)

    elif text.startswith("/meta"):
        parts = text.split()
        numero = parts[1] if len(parts) > 1 else ""
        response = handle_meta(telegram_id, numero)

    elif text.startswith("/vincular"):
        parts = text.split()
        code = parts[1] if len(parts) > 1 else ""
        response = handle_vincular(telegram_id, code)

    elif text.startswith("/"):
        response = "Comando no reconocido. Escribe /start para ver las opciones."

    else:
        response = await handle_free_message(telegram_id, text)  # async: llama IA

    return {"chat_id": chat_id, "text": response, "handled": True}


# ── Handlers individuales ─────────────────────────────────────────────────────

def _get_linked_user(telegram_id: int | str):
    """Helper síncrono: devuelve el User vinculado o None."""
    from bot.nura_bridge import get_user_by_telegram_id
    return get_user_by_telegram_id(telegram_id)


def handle_start(telegram_id: int | str, username: str) -> str:
    """
    Saluda al usuario y le muestra el menú de comandos.

    Si el usuario aún no está vinculado, le explica cómo hacerlo.
    """
    user = _get_linked_user(telegram_id)
    name = f"@{username}" if username else "usuario"

    if user is None:
        return (
            f"¡Hola, {name}! Soy *Nura*, tu tutor de aprendizaje adaptativo. 🧠\n\n"
            "Para usar todas las funciones, vincula tu cuenta:\n"
            "1. Abre la app en Streamlit.\n"
            "2. Ve a *Mi perfil* → *Vincular Telegram*.\n"
            "3. Copia el código y envíamelo aquí con:\n"
            "   `/vincular XXXXXX`"
        )

    return (
        f"¡Bienvenido de vuelta, *{user.username}*! 👋\n\n"
        "Comandos disponibles:\n"
        "• /capturar [término] — aprende algo nuevo\n"
        "• /repasar — conceptos pendientes de hoy\n"
        "• /streak — tu racha y progreso\n"
        "• /meta [número] — cambia tu meta diaria\n"
        "• O simplemente escríbeme lo que quieras aprender 💡"
    )


async def handle_capturar(telegram_id: int | str, texto: str) -> str:
    """
    Captura un concepto nuevo invocando el grafo de Nura en un hilo separado.

    Usa `asyncio.to_thread` para ejecutar `run_tutor` (síncrona, puede tardar
    30+ s con Gemini) sin bloquear el event loop de FastAPI.

    Si el usuario no está vinculado, retorna inmediatamente sin llamar a la IA.
    """
    user = _get_linked_user(telegram_id)
    if user is None:
        return _msg_no_vinculado()

    if not texto:
        return "¿Qué término quieres capturar? Usa: `/capturar [término]`"

    from bot.nura_bridge import run_tutor
    respuesta = await asyncio.to_thread(run_tutor, user.id, texto)
    return f"✅ Concepto capturado:\n\n{respuesta}"


def handle_repasar(telegram_id: int | str) -> str:
    """
    Muestra los conceptos pendientes de repaso según SM-2.

    Si no hay pendientes, lo indica.
    """
    user = _get_linked_user(telegram_id)
    if user is None:
        return _msg_no_vinculado()

    from bot.nura_bridge import get_pending_concepts
    conceptos = get_pending_concepts(user.id)

    if not conceptos:
        return "🎉 ¡No tienes conceptos pendientes para hoy! Vuelve mañana."

    lineas = [f"📚 *{c.term}* — nivel {c.mastery_level}/5" for c in conceptos[:10]]
    respuesta = "\n".join(lineas)
    if len(conceptos) > 10:
        respuesta += f"\n…y {len(conceptos) - 10} más."
    return f"Tienes *{len(conceptos)}* concepto(s) para repasar hoy:\n\n{respuesta}"


def handle_streak(telegram_id: int | str) -> str:
    """
    Muestra la racha actual y el progreso de la meta diaria.
    """
    user = _get_linked_user(telegram_id)
    if user is None:
        return _msg_no_vinculado()

    from db.operations import get_streak, get_today_count, get_daily_goal

    streak  = get_streak(user.id)
    today   = get_today_count(user.id)
    goal    = get_daily_goal(user.id)
    pct     = min(int(today / max(goal, 1) * 100), 100)
    dias    = "día" if streak == 1 else "días"
    barra   = "█" * (pct // 10) + "░" * (10 - pct // 10)

    return (
        f"🔥 *{streak} {dias} seguido{'s' if streak != 1 else ''}*\n\n"
        f"Meta de hoy: {today}/{goal} conceptos\n"
        f"`[{barra}]` {pct}%"
    )


def handle_meta(telegram_id: int | str, numero: str) -> str:
    """
    Actualiza la meta diaria de conceptos del usuario.
    """
    user = _get_linked_user(telegram_id)
    if user is None:
        return _msg_no_vinculado()

    if not numero.isdigit():
        return "Uso: `/meta [número]`  Ejemplo: `/meta 5`"

    goal = int(numero)
    if goal < 1 or goal > 50:
        return "La meta debe estar entre 1 y 50 conceptos por día."

    from db.operations import update_daily_goal
    update_daily_goal(user.id, goal)
    return f"✅ Meta diaria actualizada a *{goal}* concepto{'s' if goal != 1 else ''} por día."


def handle_vincular(telegram_id: int | str, code: str) -> str:
    """
    Vincula el telegram_id con la cuenta Nura usando el código generado en la app.
    """
    if not code:
        return (
            "Para vincular tu cuenta:\n"
            "1. Abre Nura en Streamlit.\n"
            "2. Ve a *Mi perfil* → *Vincular Telegram*.\n"
            "3. Copia el código y envíalo aquí con:\n"
            "   `/vincular XXXXXX`"
        )

    from bot.nura_bridge import link_user
    ok = link_user(telegram_id, code)
    if ok:
        return "✅ ¡Cuenta vinculada con éxito! Ya puedes usar todos los comandos de Nura."
    return "❌ Código incorrecto o expirado. Genera uno nuevo desde la app."


async def handle_free_message(telegram_id: int | str, texto: str) -> str:
    """
    Envía un mensaje libre al tutor de Nura con el contexto completo del usuario.

    Usa `asyncio.to_thread` para que la llamada a Gemini (síncrona, lenta)
    no bloquee el event loop de FastAPI.
    """
    user = _get_linked_user(telegram_id)
    if user is None:
        return _msg_no_vinculado()

    from bot.nura_bridge import run_tutor
    return await asyncio.to_thread(run_tutor, user.id, texto)


def _msg_no_vinculado() -> str:
    """Mensaje estándar para usuarios no vinculados."""
    return (
        "⚠️ Tu cuenta de Telegram no está vinculada con Nura.\n\n"
        "Para vincularla:\n"
        "1. Abre la app en Streamlit.\n"
        "2. Ve a *Mi perfil* → *Vincular Telegram*.\n"
        "3. Envíame el código con: `/vincular XXXXXX`"
    )
