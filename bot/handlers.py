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


# ── Sprint 30: examen por Telegram ───────────────────────────────────────────


def _user_exam_categories(user_id: int) -> list[str]:
    from db.operations import get_all_concepts

    cats: set[str] = set()
    for c in get_all_concepts(user_id=user_id):
        if getattr(c, "is_classified", False) and c.flashcard_front:
            cats.add(c.category or "Sin categoría")
    return sorted(cats)


def _match_category(available: list[str], needle: str) -> str | None:
    n = (needle or "").strip().lower()
    if not n:
        return None
    for a in available:
        if a.lower() == n:
            return a
    return None


def _parse_exam_answer_letter(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    if t[0] in ("a", "b", "c", "d"):
        return t[0]
    if t in ("1", "2", "3", "4"):
        return "abcd"[int(t) - 1]
    return None


def _format_telegram_question(q: dict, index0: int) -> str:
    opts = q.get("options") or []
    lines = [f"📝 Pregunta *{index0 + 1}/10*", "", q.get("question", "")]
    for i, letter in enumerate("abcd"):
        if i < len(opts):
            lines.append(f"{letter}) {opts[i]}")
    lines.extend(["", "Respondé con *a*, *b*, *c* o *d* (o 1–4)."])
    return "\n".join(lines)


def try_handle_exam_answer(user_id: int, text: str) -> str | None:
    """
    Si hay sesión de examen activa, registra la respuesta o devuelve la siguiente pregunta.

    Retorna None si no aplica (no hay sesión).
    """
    from agents.exam_agent import evaluate_exam
    from db.operations import (
        delete_exam_session,
        get_exam_session_for_user,
        save_certification,
        update_exam_session_progress,
    )

    sess = get_exam_session_for_user(user_id)
    if sess is None:
        return None

    letter = _parse_exam_answer_letter(text)
    if letter is None:
        return (
            "📝 *Examen en curso* — enviá solo la letra *a*, *b*, *c* o *d* "
            "(o un dígito del 1 al 4)."
        )

    qs = sess["questions"]
    if not isinstance(qs, list) or len(qs) != 10:
        delete_exam_session(sess["id"])
        return "La sesión de examen no es válida. Iniciá de nuevo con `/examen [categoría]`."

    ans = list(sess["answers"])
    if len(ans) >= 10:
        delete_exam_session(sess["id"])
        return None

    ans.append(letter)
    update_exam_session_progress(sess["id"], ans)

    if len(ans) < 10:
        return _format_telegram_question(qs[len(ans)], len(ans))

    result = evaluate_exam(qs, ans)
    delete_exam_session(sess["id"])
    cat = sess["category"]
    if result["passed"]:
        save_certification(user_id, cat, result["score"], True)

    lines = [
        "🏁 *Resultado del examen*",
        f"Categoría: *{cat}*",
        f"Aciertos: *{result['correct']}*/{result['total']} ({result['score']:.0%})",
    ]
    if result["passed"]:
        lines.append("✅ ¡Certificaste esta categoría! (umbral ≥ 80%).")
    else:
        lines.append("Todavía no alcanzaste el 80%. Seguí practicando en la app.")
        wrong_concepts: list[str] = []
        for i, q in enumerate(qs):
            if i < len(ans) and ans[i] != str(q.get("correct", "")).strip().lower():
                cx = str(q.get("concept") or "").strip()
                if cx and cx not in wrong_concepts:
                    wrong_concepts.append(cx)
        if wrong_concepts:
            lines.append("")
            lines.append("*Conceptos para reforzar:*")
            for cx in wrong_concepts[:10]:
                lines.append(f"• {cx}")
    return "\n".join(lines)


async def handle_examen_command(
    _telegram_id: int | str,
    user_id: int,
    category_arg: str,
) -> str:
    """Lista categorías o inicia examen y devuelve la primera pregunta."""
    from agents.exam_agent import generate_exam
    from db.operations import get_all_concepts, get_user_by_id, replace_exam_session

    cats = _user_exam_categories(user_id)
    if not category_arg.strip():
        if not cats:
            return (
                "No tenés categorías con conceptos clasificados para examen.\n"
                "Capturá y clasificá conceptos en la app primero."
            )
        body = (
            "Podés rendir un examen por categoría. Usá:\n`/examen [categoría]`\n\n"
            "*Categorías disponibles:*\n"
        )
        body += "\n".join(f"• `{c}`" for c in cats)
        return body

    resolved = _match_category(cats, category_arg)
    if resolved is None:
        return (
            f"No reconozco la categoría «{category_arg.strip()}».\n"
            "Escribí `/examen` para ver la lista."
        )

    concepts_objs = [
        c
        for c in get_all_concepts(user_id=user_id)
        if (c.category or "Sin categoría") == resolved
        and getattr(c, "is_classified", False)
        and c.flashcard_front
    ]
    if not concepts_objs:
        return f"No hay conceptos listos en «{resolved}» para armar el examen."

    concepts_payload = [
        {
            "term":        c.term,
            "explanation": c.explanation or "",
            "category":    c.category or "",
        }
        for c in concepts_objs
    ]
    user = get_user_by_id(user_id)
    profile: dict = {}
    if user is not None:
        profile = {
            "profession":    getattr(user, "profession", "") or "",
            "learning_area": getattr(user, "learning_area", "") or "",
            "tech_level":    getattr(user, "tech_level", "") or "",
        }

    questions = await asyncio.to_thread(
        generate_exam,
        resolved,
        concepts_payload,
        profile,
    )
    if not questions:
        return "No pude generar el examen ahora. Probá de nuevo más tarde."

    replace_exam_session(user_id, resolved, questions)
    intro = (
        f"📝 *Examen: {resolved}*\n"
        "10 preguntas. Aprobación: *80%* o más.\n\n"
    )
    return intro + _format_telegram_question(questions[0], 0)


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

    elif text.startswith("/recordatorio"):
        parts = text.split()
        time_str = parts[1] if len(parts) > 1 else ""
        response = handle_recordatorio(telegram_id, time_str)

    elif text.startswith("/simple"):
        user = _get_linked_user(telegram_id)
        if user is None:
            response = _msg_no_vinculado()
        else:
            response = handle_simple(telegram_id, user.id)

    elif text.startswith("/arbol"):
        user = _get_linked_user(telegram_id)
        if user is None:
            response = _msg_no_vinculado()
        else:
            category = text[len("/arbol"):].strip() or None
            response = handle_arbol(telegram_id, user.id, category)

    elif text.startswith("/examen"):
        user = _get_linked_user(telegram_id)
        if user is None:
            response = _msg_no_vinculado()
        else:
            cat_arg = text[len("/examen"):].strip()
            response = await handle_examen_command(telegram_id, user.id, cat_arg)

    elif text.startswith("/podcast"):
        user = _get_linked_user(telegram_id)
        if user is None:
            response = _msg_no_vinculado()
        else:
            return await handle_podcast(chat_id, user.id)   # retorna dict completo

    elif text.startswith("/audio"):
        user = _get_linked_user(telegram_id)
        if user is None:
            response = _msg_no_vinculado()
        else:
            term = text[len("/audio"):].strip()
            return await handle_audio(chat_id, user.id, term)  # retorna dict completo

    elif text.startswith("/"):
        response = "Comando no reconocido. Escribe /start para ver las opciones."

    else:
        user_ex = _get_linked_user(telegram_id)
        if user_ex is not None:
            exam_reply = try_handle_exam_answer(user_ex.id, text)
            if exam_reply is not None:
                return {"chat_id": chat_id, "text": exam_reply, "handled": True}
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
        "• /examen [categoría] — certificación por categoría\n"
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


def handle_recordatorio(telegram_id: int | str, time_str: str) -> str:
    """
    Configura la hora de recordatorio diario del usuario.

    Valida el formato HH:MM antes de guardar. Responde con confirmación
    o con un mensaje de error si el formato es inválido.
    """
    user = _get_linked_user(telegram_id)
    if user is None:
        return _msg_no_vinculado()

    if not time_str:
        return "Uso: `/recordatorio HH:MM`  Ejemplo: `/recordatorio 08:00`"

    from db.operations import set_reminder_time
    try:
        set_reminder_time(user.id, time_str)
    except ValueError:
        return (
            f"❌ Formato inválido: `{time_str}`. "
            "Usa HH:MM (00:00 – 23:59).  Ejemplo: `/recordatorio 08:00`"
        )

    return f"✅ Te recordaré todos los días a las {time_str}."


def handle_simple(telegram_id: int | str, user_id: int) -> str:
    """
    Simplifica la última respuesta del tutor guardada para el usuario.

    Si no hay respuesta previa en BD, devuelve un mensaje amigable.
    """
    from db.operations import get_last_tutor_response, get_user_by_id
    from agents.tutor_agent import simplify_explanation

    last = get_last_tutor_response(user_id)
    if not last:
        return "Primero hazme una pregunta y luego usa /simple"

    user = get_user_by_id(user_id)
    profile: dict = {}
    if user is not None:
        profile = {
            "profession":    getattr(user, "profession", "") or "",
            "learning_area": getattr(user, "learning_area", "") or "",
            "tech_level":    getattr(user, "tech_level", "") or "",
        }

    return simplify_explanation(last, profile)


def handle_arbol(
    telegram_id: int | str,
    user_id: int,
    category: "str | None" = None,
) -> str:
    """
    Genera una representación ASCII del árbol jerárquico del usuario.

    Parámetros
    ----------
    telegram_id : ID de Telegram (no se usa en la lógica, solo para firma).
    user_id     : ID del usuario en Nura.
    category    : Si se proporciona, filtra por esa categoría.

    Devuelve
    --------
    str — árbol en texto ASCII listo para enviar a Telegram.
    """
    from db.operations import get_concept_tree

    tree = get_concept_tree(user_id, category=category)

    if not tree:
        if category:
            return f"🌳 No hay jerarquías registradas para la categoría '{category}'."
        return (
            "🌳 Aún no hay jerarquías registradas.\n"
            "Sigue capturando conceptos y Nura construirá el árbol automáticamente."
        )

    lines: list[str] = []
    if category:
        lines.append(f"🌳 Árbol jerárquico — {category}\n")
    else:
        lines.append("🌳 Árbol jerárquico completo\n")

    def _render_node(node: dict, prefix: str = "", is_last: bool = True) -> None:
        children = node.get("children", {})
        items    = list(children.items())
        for i, (child_term, child_node) in enumerate(items):
            last      = i == len(items) - 1
            connector = "└──" if last else "├──"
            rel       = child_node.get("relation", "")
            rel_txt   = f" [{rel}]" if rel else ""
            lines.append(f"{prefix}{connector} {child_term}{rel_txt}")
            extension = "    " if last else "│   "
            _render_node(child_node, prefix=prefix + extension, is_last=last)

    for root_term, root_node in tree.items():
        lines.append(f"📌 {root_term}")
        _render_node(root_node)
        lines.append("")

    result = "\n".join(lines).rstrip()
    # Telegram tiene límite de 4096 caracteres
    if len(result) > 4000:
        result = result[:4000] + "\n…(truncado)"
    return result


async def handle_podcast(telegram_id: int | str, user_id: int) -> dict:
    """
    Genera el resumen diario del usuario como nota de voz.

    Llama a generate_podcast_text para construir el guión y text_to_speech
    para convertirlo a OGG/OPUS.  Si TTS falla, hace fallback a texto.

    Parámetros
    ----------
    telegram_id : ID de Telegram (= chat_id en chats privados).
    user_id     : ID del usuario en Nura.

    Devuelve
    --------
    dict con claves: chat_id, type ('voice'|'text'), audio_bytes o text, handled.
    """
    from bot.tts import text_to_speech, generate_podcast_text

    text = generate_podcast_text(user_id)
    try:
        audio_bytes = await asyncio.to_thread(text_to_speech, text)
        return {
            "chat_id":     telegram_id,
            "audio_bytes": audio_bytes,
            "type":        "voice",
            "handled":     True,
        }
    except Exception as exc:
        print(f"[TTS] Fallback a texto en /podcast: {exc}")
        return {"chat_id": telegram_id, "text": text, "type": "text", "handled": True}


async def handle_audio(telegram_id: int | str, user_id: int, term: str) -> dict:
    """
    Explica un término como nota de voz.

    Si term está vacío, retorna un mensaje de ayuda de inmediato.
    Genera la explicación con el tutor y convierte a OGG/OPUS.
    Si TTS falla, hace fallback a texto.

    Parámetros
    ----------
    telegram_id : ID de Telegram (= chat_id en chats privados).
    user_id     : ID del usuario en Nura.
    term        : Término a explicar; vacío si el usuario no lo proporcionó.

    Devuelve
    --------
    dict con claves: chat_id, type ('voice'|'text'), audio_bytes o text, handled.
    """
    if not term:
        return {
            "chat_id": telegram_id,
            "text":    "¿Qué término quieres que te explique? Usa: `/audio LangGraph`",
            "type":    "text",
            "handled": True,
        }

    from bot.tts import text_to_speech, generate_audio_explanation

    explanation = ""
    try:
        explanation = await asyncio.to_thread(generate_audio_explanation, user_id, term)
        audio_bytes = await asyncio.to_thread(text_to_speech, explanation)
        return {
            "chat_id":     telegram_id,
            "audio_bytes": audio_bytes,
            "type":        "voice",
            "handled":     True,
        }
    except Exception as exc:
        print(f"[TTS] Fallback a texto en /audio: {exc}")
        fallback = explanation or f"No pude generar la explicación de '{term}'."
        return {"chat_id": telegram_id, "text": fallback, "type": "text", "handled": True}


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
