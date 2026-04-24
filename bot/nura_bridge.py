"""
bot/nura_bridge.py
==================
Puente entre el bot de Telegram y los módulos internos de Nura.

Responsabilidades
-----------------
- Buscar / vincular usuarios por telegram_id.
- Generar y validar códigos de vinculación temporales (6 dígitos, 10 min).
- Invocar el grafo LangGraph (modo tutor) en nombre del usuario.
- Consultar conceptos pendientes de repaso según SM-2.

Diseño
------
Todas las funciones son puras respecto al transporte HTTP: no saben nada de
Telegram ni de FastAPI.  Así son fáciles de testear con mocks de BD.

Las importaciones pesadas (LangGraph, agentes) se hacen dentro de cada
función para que los tests que mockean db.operations puedan importar este
módulo sin cargar el grafo.
"""

from __future__ import annotations

import os
import random
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.models import Concept, User

# Garantiza que los imports de db/ y agents/ funcionen cuando el bot
# se ejecuta desde cualquier directorio (ej. Railway, uvicorn desde raíz).
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── Vinculación de usuarios ────────────────────────────────────────────────────

def get_user_by_telegram_id(telegram_id: int | str) -> "User | None":
    """
    Busca el usuario de Nura vinculado a este telegram_id.

    Devuelve
    --------
    User si está vinculado, None si no.
    """
    from db.operations import get_user_by_telegram_id as _get
    return _get(str(telegram_id))


def generate_link_code(user_id: int) -> str:
    """
    Genera un código numérico de 6 dígitos, lo persiste en BD y lo devuelve.

    El código expira en 10 minutos.  Si ya había un código previo, se sobreescribe.

    Parámetros
    ----------
    user_id : ID del usuario en Nura que solicita el código.

    Devuelve
    --------
    str — código de 6 dígitos (ej. "482031").
    """
    from db.operations import save_link_code

    code   = "".join(random.choices(string.digits, k=6))
    expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
    save_link_code(user_id, code, expiry)
    return code


def link_user(telegram_id: int | str, link_code: str) -> bool:
    """
    Vincula un telegram_id con el usuario cuyo link_code coincide y es válido.

    Parámetros
    ----------
    telegram_id : ID de Telegram del usuario.
    link_code   : Código de 6 dígitos enviado desde la app Streamlit.

    Devuelve
    --------
    True si la vinculación fue exitosa, False si el código es incorrecto o expiró.
    """
    from db.operations import get_user_by_link_code, save_link_code, set_telegram_id

    user = get_user_by_link_code(link_code)
    if user is None:
        return False

    set_telegram_id(user.id, str(telegram_id))
    # Invalidar el código usado: limpiar link_code y expiry
    save_link_code(user.id, "", "")
    return True


# ── Conceptos y repaso ─────────────────────────────────────────────────────────

def get_pending_concepts(user_id: int) -> list["Concept"]:
    """
    Devuelve los conceptos del usuario pendientes de repaso hoy según SM-2.

    Parámetros
    ----------
    user_id : ID del usuario en Nura.

    Devuelve
    --------
    list[Concept] — puede estar vacía si no hay pendientes.
    """
    from db.operations import get_concepts_due_today
    return get_concepts_due_today(user_id=user_id)


# ── Tutor ─────────────────────────────────────────────────────────────────────

def run_tutor(user_id: int, mensaje: str) -> str:
    """
    Invoca el grafo LangGraph en modo tutor y devuelve la respuesta como texto.

    Construye el perfil del usuario para personalizar los prompts del tutor,
    luego llama a graph.invoke() de forma síncrona (el bot no usa Streamlit).

    Parámetros
    ----------
    user_id : ID del usuario en Nura.
    mensaje : Pregunta o término enviado por el usuario desde Telegram.

    Devuelve
    --------
    str — respuesta del tutor.  En caso de error, mensaje amigable.
    """
    from db.operations import get_user_by_id
    from agents.graph import build_graph

    # Cargar perfil del usuario para contextualizar el tutor
    user = get_user_by_id(user_id)
    user_profile: dict = {}
    if user:
        user_profile = {
            "profession":    getattr(user, "profession",    ""),
            "learning_area": getattr(user, "learning_area", ""),
            "tech_level":    getattr(user, "tech_level",    ""),
        }

    try:
        graph = build_graph()
        result = graph.invoke({
            "user_input":   mensaje,
            "user_id":      user_id,
            "user_profile": user_profile,
            "mode":         "",
            "history":      [],
            "response":     "",
        })
        return result.get("response") or result.get("message", "Sin respuesta.")
    except Exception as exc:
        return f"Error al contactar al tutor: {exc!s:.200}"
