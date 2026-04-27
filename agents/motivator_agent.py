"""
agents/motivator_agent.py
=========================
Generador de mensajes motivadores personalizados al final de sesión.

El agente combina lógica determinista de clasificación de eventos con una
llamada a Gemini para producir un mensaje corto, cercano y basado en los
datos reales de la sesión.  Si Gemini falla, usa mensajes de respaldo
predefinidos para garantizar que el usuario siempre reciba retroalimentación.

Flujo
-----
1. get_session_stats(user_id) → estadísticas de la sesión.
2. _determine_event_type(stats) → clasifica el evento con prioridad fija.
3. _gemini_message(tipo, stats) → genera el mensaje vía LLM (puede fallar).
4. Si LLM falla → _fallback_message(tipo) → mensaje determinista.

Tipos de evento (en orden de prioridad descendente)
-----------------------------------------------------
primera_sesion  — es la primera sesión del usuario.
racha_7         — lleva 7 o más días consecutivos activos.
conexiones_3    — creó 3 o más conexiones hoy.
conceptos_5     — capturó 5 o más conceptos hoy.
solo_repaso     — hoy solo repasó (sin conceptos nuevos ni quiz).
quiz_bajo       — tuvo un quiz con score < 60%.
default         — sesión normal sin evento destacado.
"""

from __future__ import annotations

import os

# ── Mensajes de respaldo deterministas ────────────────────────────────────────

_FALLBACK: dict[str, str] = {
    "primera_sesion": (
        "Tu primera estrella en el mapa. "
        "Todo gran universo de conocimiento empieza con un punto."
    ),
    "racha_7": (
        "Siete días seguidos. "
        "Tu constelación crece con disciplina, no con suerte."
    ),
    "conexiones_3": (
        "Hoy no solo aprendiste — conectaste. "
        "Eso es lo que convierte información en comprensión real."
    ),
    "conceptos_5": (
        "Tu mapa creció hoy. "
        "Cada nodo nuevo es una estrella que ilumina las que ya tenías."
    ),
    "solo_repaso": (
        "Repasar es recordar. "
        "Hoy fortaleciste lo que ya sabías — eso es conocimiento duradero."
    ),
    "quiz_bajo": (
        "El error es parte del mapa. "
        "Ahora sabes exactamente qué nodo necesita más luz."
    ),
    "default": (
        "Otro día, otro nodo. "
        "Tu constelación de conocimiento sigue creciendo."
    ),
}

# Orden de prioridad para la clasificación de eventos
_EVENT_PRIORITY = [
    "primera_sesion",
    "racha_7",
    "conexiones_3",
    "conceptos_5",
    "solo_repaso",
    "quiz_bajo",
    "default",
]


# ── Lógica determinista ───────────────────────────────────────────────────────

def _determine_event_type(stats: dict) -> str:
    """
    Clasifica el tipo de evento de la sesión con prioridad fija.

    Evalúa las condiciones en orden descendente de prioridad y retorna el
    primer tipo cuya condición sea verdadera.

    Parámetros
    ----------
    stats : dict devuelto por get_session_stats(), más quiz_score opcional.

    Devuelve
    --------
    str — uno de los valores de _EVENT_PRIORITY.
    """
    quiz_score     = stats.get("quiz_score")
    conceptos_hoy  = stats.get("conceptos_hoy", 0)
    conexiones_hoy = stats.get("conexiones_hoy", 0)
    repasados_hoy  = stats.get("repasados_hoy", 0)
    racha          = stats.get("racha", 0)

    if stats.get("es_primera_sesion"):
        return "primera_sesion"
    if racha >= 7:
        return "racha_7"
    if conexiones_hoy >= 3:
        return "conexiones_3"
    if conceptos_hoy >= 5:
        return "conceptos_5"
    if repasados_hoy > 0 and conceptos_hoy == 0 and quiz_score is None:
        return "solo_repaso"
    if quiz_score is not None and quiz_score < 60:
        return "quiz_bajo"
    return "default"


def _fallback_message(event_type: str) -> str:
    """
    Retorna el mensaje de respaldo para un tipo de evento dado.

    Parámetros
    ----------
    event_type : Uno de los tipos definidos en _EVENT_PRIORITY.

    Devuelve
    --------
    str — mensaje motivador predefinido.
    """
    return _FALLBACK.get(event_type, _FALLBACK["default"])


def _gemini_message(event_type: str, stats: dict) -> str:
    """
    Genera un mensaje motivador personalizado llamando a Gemini.

    Construye un prompt con el tipo de evento y las estadísticas reales de la
    sesión.  Si la llamada falla por cualquier razón, lanza la excepción para
    que el llamador use el mensaje de respaldo.

    Parámetros
    ----------
    event_type : Tipo de evento determinado por _determine_event_type().
    stats      : Estadísticas de la sesión del usuario.

    Devuelve
    --------
    str — mensaje motivador generado por el LLM, limpio de comillas externas.

    Lanza
    -----
    Exception si la llamada a Gemini falla.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    from agents.gemini_llm import GEMINI_REQUEST_TIMEOUT_SEC

    stats_str = (
        f"conceptos_hoy={stats.get('conceptos_hoy', 0)}, "
        f"conexiones_hoy={stats.get('conexiones_hoy', 0)}, "
        f"repasados_hoy={stats.get('repasados_hoy', 0)}, "
        f"racha={stats.get('racha', 0)} días, "
        f"quiz_score={stats.get('quiz_score')}"
    )

    prompt = (
        "Eres Nura. Genera un mensaje motivador de máximo 2 líneas para un "
        "usuario que acaba de terminar una sesión de aprendizaje. "
        f"Tipo de evento: {event_type}. "
        f"Datos: {stats_str}. "
        "Usa metáforas de constelaciones, nodos y conocimiento conectado. "
        "Tono cercano y motivador. Nunca uses listas ni emojis excesivos. "
        "Sé específico con los datos reales. "
        "Responde SOLO con el mensaje, sin comillas ni prefijos."
    )

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.7,
        request_timeout=GEMINI_REQUEST_TIMEOUT_SEC,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    text = response.content.strip().strip('"').strip("'")
    return text if text else _fallback_message(event_type)


# ── Función pública ───────────────────────────────────────────────────────────

def get_motivational_message(user_id: int = 1, quiz_score: float | None = None) -> str:
    """
    Retorna un mensaje motivador personalizado para el usuario al final de sesión.

    Combina estadísticas de la sesión con clasificación determinista de eventos
    y generación LLM para producir un mensaje cercano y específico.  Si Gemini
    no está disponible o falla, retorna el mensaje de respaldo correspondiente
    sin propagar el error.

    Parámetros
    ----------
    user_id    : ID del usuario (default=1).
    quiz_score : Score del último quiz en porcentaje (0-100), o None si no hubo.

    Devuelve
    --------
    str — mensaje motivador de 1-2 líneas listo para mostrar al usuario.
    """
    from db.operations import get_session_stats

    stats = get_session_stats(user_id=user_id)
    stats["quiz_score"] = quiz_score  # inyectar score externo

    event_type = _determine_event_type(stats)

    try:
        return _gemini_message(event_type, stats)
    except Exception:
        return _fallback_message(event_type)
