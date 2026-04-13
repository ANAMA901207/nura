"""
agents/classifier_agent.py
==========================
Segundo nodo del grafo: enriquece el concepto recién capturado con su
clasificación semántica completa usando Gemini.

Recibe el concepto en blanco (solo term y context) del estado, llama a
classify_concept() para obtener categoría, subcategoría, explicación,
analogía y flashcards, y persiste esos datos en la BD via
update_concept_classification().  El concepto queda marcado is_classified=True.

Manejo de errores (Sprint 5)
-----------------------------
Si classify_concept() lanza ClassificationError (cuota agotada, timeout,
API no disponible, etc.), el nodo NO actualiza el concepto en la BD:
el concepto permanece con is_classified=False para que el usuario pueda
reintentarlo más tarde desde la UI.  El pipeline continúa con un mensaje
amigable en state.response.
"""

from __future__ import annotations

import json

from db.operations import update_concept_classification
from agents.state import NuraState
from tools.classifier_tool import classify_concept, ClassificationError

# Sprint 19: tools formales disponibles para bind_tools() en invocaciones
# externas y para registro en ToolNode del grafo.
try:
    from tools.db_tools import NURA_TOOLS as _NURA_TOOLS  # noqa: F401
except ImportError:
    _NURA_TOOLS = []


def _parse_tech_level(tech_level_str: str) -> dict[str, str]:
    """
    Convierte el campo tech_level en un dict área → nivel.

    Sprint 15 introdujo el formato JSON serializado para soportar niveles
    distintos por área (p. ej. '{"IA y tecnología": "Básico", ...}').
    Esta función acepta también el formato antiguo (cadena simple como
    "Intermedio") devolviéndolo como {"general": "Intermedio"}, de modo que
    el código que lo consume no necesita distinguir entre versiones.

    Parámetros
    ----------
    tech_level_str : Valor del campo tech_level tal como se leyó de la BD.

    Devuelve
    --------
    dict con área → nivel.  Dict vacío si la cadena está vacía.
    """
    if not tech_level_str:
        return {}
    try:
        result = json.loads(tech_level_str)
        if isinstance(result, dict):
            return {str(k): str(v) for k, v in result.items()}
    except (json.JSONDecodeError, ValueError):
        pass
    # Formato legacy: nivel único como cadena plana
    return {"general": tech_level_str}

_CLASSIFICATION_FAILED_MSG = (
    "Nura no pudo clasificar este término ahora, intenta en unos minutos 🌙"
)


def classifier_agent(state: NuraState) -> dict:
    """
    Nodo de clasificación: enriquece el concepto con los datos de Gemini.

    Flujo interno — éxito
    ---------------------
    1. Recupera current_concept del estado (guardado por capture_agent).
    2. Llama a classify_concept(term, context, user_context) → dict.
    3. Combina explanation + how_it_works para no perder información útil.
    4. Persiste los campos enriquecidos vía update_concept_classification(),
       que además establece is_classified=True en la BD.
    5. Actualiza current_concept en el estado con el concepto enriquecido.

    Flujo interno — ClassificationError
    ------------------------------------
    Si classify_concept falla por cualquier razón:
    - El concepto en BD queda intacto (is_classified=False).
    - state.response recibe el mensaje amigable _CLASSIFICATION_FAILED_MSG.
    - El pipeline continúa hacia connector sin bloquear al usuario.

    Parámetros
    ----------
    state : Estado actual del grafo.  Requiere current_concept != None.

    Devuelve
    --------
    dict parcial con current_concept y response actualizados.

    Lanza
    -----
    ValueError : Si current_concept es None (nodo ejecutado fuera de orden).
    """
    concept = state.get("current_concept")
    if concept is None:
        raise ValueError(
            "classifier_agent requiere current_concept en el estado. "
            "Verifica que capture_agent se ejecutó antes en el grafo."
        )

    user_context = concept.user_context if hasattr(concept, "user_context") else ""
    user_id: int = state.get("user_id", 1)  # Sprint 11

    # Sprint 15: enriquece user_context con el perfil del usuario cuando está disponible,
    # para que el clasificador adapte los ejemplos y la terminología al contexto del usuario.
    user_profile: dict = state.get("user_profile") or {}
    profession    = user_profile.get("profession", "").strip()
    learning_area = user_profile.get("learning_area", "").strip()
    tech_level_raw = user_profile.get("tech_level", "").strip()
    if profession or learning_area or tech_level_raw:
        parts: list[str] = []
        if profession:
            parts.append(f"profesión: {profession}")
        if learning_area:
            parts.append(f"área{'s' if ',' in learning_area else ''} de interés: {learning_area}")
        if tech_level_raw:
            levels_dict = _parse_tech_level(tech_level_raw)
            if len(levels_dict) == 1:
                parts.append(f"nivel: {next(iter(levels_dict.values()))}")
            elif len(levels_dict) > 1:
                lvl_parts = [f"{lvl} en {area}" for area, lvl in levels_dict.items()]
                parts.append(f"niveles: {', '.join(lvl_parts)}")

        # Instrucción dinámica de tipo de ejemplo según profesión
        _prof_lower = profession.lower()
        _la_lower   = learning_area.lower()
        _is_tech = any(k in _la_lower for k in ("ia y", "software", "tecnolog", "desarrollo de software")) \
                   or any(k in _prof_lower for k in ("desarroll", "ingenier", "developer", "programad", "datos"))

        if any(k in _prof_lower for k in ("economista", "econom", "macroeconom")):
            example_hint = (
                "Para el campo 'example', usa un ejemplo de macroeconomía, política monetaria, "
                "mercados financieros o economía aplicada. "
                "NUNCA uses ejemplos de tecnología, APIs o software."
            )
        elif any(k in _prof_lower for k in ("banca", "crédit", "credit", "analista financ", "finanzas")):
            example_hint = (
                "Para el campo 'example', usa un ejemplo en crédito o banca. "
                "NUNCA uses ejemplos de tecnología o software."
            )
        elif any(k in _prof_lower for k in ("contador", "contable", "contabilid", "auditor")):
            example_hint = (
                "Para el campo 'example', usa un ejemplo de contabilidad, NIIF o auditoría. "
                "NUNCA uses ejemplos de tecnología o software."
            )
        elif any(k in _prof_lower for k in ("desarroll", "ingenier", "developer", "softwar")):
            example_hint = "Para el campo 'example', usa un ejemplo en código o arquitectura de software."
        elif any(k in _prof_lower for k in ("ux", "diseñ", "design", "experiencia")):
            example_hint = "Para el campo 'example', usa un ejemplo en diseño de experiencia de usuario."
        elif any(k in _prof_lower for k in ("emprend", "negoci", "product", "market")):
            example_hint = (
                "Para el campo 'example', usa un ejemplo en producto o negocio. "
                "NUNCA uses ejemplos de tecnología o código."
            )
        elif "estudiant" in _prof_lower or "student" in _prof_lower:
            example_hint = "Para el campo 'example', usa un ejemplo académico o conceptual."
        elif not _is_tech and (profession or learning_area):
            example_hint = (
                "Para el campo 'example', usa un ejemplo del mundo real relevante para el usuario. "
                "NUNCA uses analogías de tecnología, APIs, código o ingeniería de software."
            )
        elif profession:
            example_hint = "Para el campo 'example', usa un ejemplo práctico relevante para el usuario."
        else:
            example_hint = ""

        profile_hint = (
            "Perfil del usuario — "
            + ", ".join(parts)
            + ". Adapta los ejemplos y la terminología a su contexto."
        )
        if example_hint:
            profile_hint = f"{profile_hint} {example_hint}"
        user_context = f"{user_context}\n{profile_hint}".strip() if user_context else profile_hint

    try:
        data = classify_concept(
            term=concept.term,
            context=concept.context,
            user_context=user_context,
        )
    except ClassificationError:
        # Fallo controlado: el concepto queda sin clasificar para reintento posterior
        return {
            "current_concept": concept,  # sin cambios, is_classified sigue en False
            "response": _CLASSIFICATION_FAILED_MSG,
        }

    # Combina explanation y how_it_works para no perder información
    explanation = data.get("explanation", "")
    how_it_works = data.get("how_it_works", "")
    if how_it_works:
        explanation = f"{explanation}\n\nCómo funciona: {how_it_works}".strip()

    # Persiste la clasificación completa y marca is_classified=True
    updated_concept = update_concept_classification(
        concept.id,
        {
            "category":       data.get("category", ""),
            "subcategory":    data.get("subcategory", ""),
            "explanation":    explanation,
            "examples":       data.get("example", ""),
            "analogy":        data.get("analogy", ""),
            "flashcard_front": data.get("flashcard_front", ""),
            "flashcard_back":  data.get("flashcard_back", ""),
        },
        user_id=user_id,
    )

    return {
        "current_concept": updated_concept,
        "response": (
            f"'{updated_concept.term}' clasificado como "
            f"'{updated_concept.category} / {updated_concept.subcategory}'."
        ),
    }
