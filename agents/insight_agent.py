"""
agents/insight_agent.py
=======================
Agente de insights adaptativos de Nura.

Se activa con mode='insight' al inicio de la sesión diaria del usuario.
Analiza los patrones de aprendizaje de la BD y genera un mensaje de bienvenida
personalizado de máximo 3 líneas, con tono amigable y motivador.

Lógica de activación
--------------------
- < 5 conceptos clasificados → mensaje de bienvenida estático sin llamar a la API.
- ≥ 5 conceptos clasificados → llama a Gemini con el contexto del perfil del usuario.
- Sin GOOGLE_API_KEY o error de API → fallback a mensaje estático con datos reales.

El resultado se guarda en state['insight_message'] y también en state['response']
para compatibilidad con el renderizado genérico de la UI.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from agents.state import NuraState
from db.operations import (
    get_all_concepts,
    get_weak_categories,
    get_weekly_insight_data,
)

load_dotenv(Path(__file__).parent.parent / ".env")

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

_MIN_CONCEPTS_FOR_INSIGHT = 5

_WELCOME_EMPTY = (
    "¡Bienvenido a Nura! 🧠 Empieza capturando tu primer concepto — "
    "escribe cualquier término que quieras aprender. "
    "Cuantos más conceptos captures, mejor personalizaré tu experiencia."
)

_INSIGHT_SYSTEM_PROMPT = (
    "Eres Nura, tutor adaptativo. "
    "Genera un mensaje de bienvenida personalizado de máximo 3 líneas. "
    "Tono: amigable, motivador y cercano — como un tutor que conoce bien al alumno. "
    "Incluye: qué aprendió recientemente, su área más débil y una sugerencia concreta "
    "de qué hacer hoy. No uses listas ni asteriscos, solo texto conversacional fluido."
)


def insight_agent(state: NuraState) -> dict:
    """
    Genera un mensaje de bienvenida personalizado basado en los patrones del usuario.

    Flujo
    -----
    1. Carga conceptos clasificados del usuario.
    2. Si hay < 5, retorna un mensaje motivador de bienvenida sin llamar a la API.
    3. Si hay ≥ 5, llama a Gemini con el perfil semanal y las categorías débiles.
    4. En caso de error de API, usa _build_static_insight() como fallback.

    Parámetros
    ----------
    state : NuraState — se lee user_id (default=1).

    Devuelve
    --------
    dict parcial con:
        insight_message (str) — mensaje generado.
        response        (str) — mismo mensaje (para compatibilidad con la UI).
    """
    user_id: int = state.get("user_id", 1)

    all_concepts = get_all_concepts(user_id=user_id)
    classified = [c for c in all_concepts if c.is_classified]

    # Pocos conceptos: bienvenida sin LLM
    if len(classified) < _MIN_CONCEPTS_FOR_INSIGHT:
        return {"insight_message": _WELCOME_EMPTY, "response": _WELCOME_EMPTY}

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        data = get_weekly_insight_data(user_id=user_id)
        msg = _build_static_insight(data)
        return {"insight_message": msg, "response": msg}

    # Llamar a Gemini con el contexto del perfil
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        data = get_weekly_insight_data(user_id=user_id)
        weak_cats = get_weak_categories(user_id=user_id)
        context = _build_insight_context(data, weak_cats, classified)

        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,
            temperature=0.7,
        )
        response = llm.invoke([
            SystemMessage(content=_INSIGHT_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ])
        msg = str(response.content).strip()
        if not msg:
            msg = _build_static_insight(data)
    except Exception:
        data = get_weekly_insight_data(user_id=user_id)
        msg = _build_static_insight(data)

    return {"insight_message": msg, "response": msg}


def _build_insight_context(data: dict, weak_cats: list[dict], classified: list) -> str:
    """
    Construye el texto de contexto que se envía a Gemini para generar el insight.

    Incluye métricas semanales, categorías débiles y los últimos conceptos aprendidos
    para que el LLM pueda generar un mensaje verdaderamente personalizado.

    Parámetros
    ----------
    data       : dict de get_weekly_insight_data().
    weak_cats  : list[dict] de get_weak_categories().
    classified : list[Concept] de conceptos clasificados del usuario.

    Devuelve
    --------
    str — contexto estructurado listo para el prompt.
    """
    lines = [
        "Datos del perfil de aprendizaje:",
        f"- Conceptos capturados esta semana: {data['conceptos_esta_semana']}",
        f"- Total conceptos clasificados: {len(classified)}",
        f"- Conceptos dominados (mastery >= 4): {data['conceptos_dominados']}",
        f"- Racha activa: {data['racha']} día(s)",
    ]
    if data["categoria_mas_fuerte"]:
        lines.append(f"- Categoría más fuerte: {data['categoria_mas_fuerte']}")
    if data["categoria_mas_debil"]:
        lines.append(f"- Categoría más débil: {data['categoria_mas_debil']}")
    if weak_cats:
        names = ", ".join(w["category"] for w in weak_cats[:3])
        lines.append(f"- Áreas que necesitan refuerzo (>2 conceptos, mastery<2.5): {names}")

    recent = sorted(classified, key=lambda c: c.created_at, reverse=True)[:3]
    if recent:
        terms = ", ".join(c.term for c in recent)
        lines.append(f"- Últimos conceptos aprendidos: {terms}")

    return "\n".join(lines)


def _build_static_insight(data: dict) -> str:
    """
    Genera un mensaje de insight sin llamar a la API, usando solo datos de la BD.

    Se usa como fallback cuando GOOGLE_API_KEY no está configurada o la llamada
    a Gemini falla por cualquier motivo.

    Parámetros
    ----------
    data : dict de get_weekly_insight_data().

    Devuelve
    --------
    str — mensaje motivador basado en los datos del usuario.
    """
    parts: list[str] = []

    if data["conceptos_esta_semana"] > 0:
        parts.append(
            f"Esta semana capturaste {data['conceptos_esta_semana']} concepto(s) nuevo(s) — ¡buen ritmo!"
        )
    if data["categoria_mas_debil"]:
        parts.append(
            f"Tu área más débil es {data['categoria_mas_debil']}. "
            f"Te sugiero dedicar hoy unos minutos a repasar esos conceptos con flashcards."
        )
    elif data["categoria_mas_fuerte"]:
        parts.append(
            f"Tu área más fuerte es {data['categoria_mas_fuerte']} — ¡sigue así! "
            "¿Quieres capturar algún concepto nuevo hoy?"
        )
    else:
        parts.append(
            "Sigue capturando conceptos para desbloquear tu perfil de aprendizaje personalizado. 🧠"
        )

    return " ".join(parts) if parts else "¡Bienvenido de vuelta! ¿Qué aprendemos hoy? 🧠"
