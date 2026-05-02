"""
agents/review_agent.py
======================
Nodo LangGraph que genera una sesión de repaso basada en el algoritmo SM-2.

Se activa cuando capture_agent detecta mode='review' (el usuario escribió
algo como "repasar" o "qué debo repasar").  A partir de Sprint 8 usa
get_concepts_due_today() para seleccionar solo los conceptos que SM-2
ha programado para hoy, en lugar de filtrar por mastery_level.
No llama a ningún modelo externo.
"""

from __future__ import annotations

from db.operations import get_all_concepts, get_concepts_due_today
from agents.state import NuraState

# Máximo de conceptos mencionados explícitamente en el mensaje de respuesta
MAX_REVIEW_CONCEPTS = 5


def _mastery_stars(level: int) -> str:
    """
    Convierte un nivel de dominio (0-5) a representación visual de estrellas.

    Parámetros
    ----------
    level : Nivel de dominio entre 0 y 5.

    Devuelve
    --------
    str con estrellas llenas y vacías, p. ej. '★★☆☆☆' para nivel 2.
    """
    return "★" * level + "☆" * (5 - level)


def review_agent(state: NuraState) -> dict:
    """
    Nodo de repaso: usa SM-2 para seleccionar los conceptos del día.

    Flujo interno (Sprint 8)
    ------------------------
    1. Llama a get_concepts_due_today() → conceptos cuyo next_review <= hoy.
    2. Si no hay ninguno, informa al usuario que está al día con SM-2.
    3. Si hay conceptos pendientes, construye un mensaje amigable indicando
       cuántos están programados por SM-2 para hoy y lista hasta MAX_REVIEW_CONCEPTS.

    Parámetros
    ----------
    state : Estado actual del grafo.  No se usa ningún campo del input.

    Devuelve
    --------
    dict parcial con response y all_concepts actualizados.
    """
    user_id: int = state.get("user_id", 1)  # Sprint 11
    all_concepts = get_all_concepts(user_id=user_id)
    due_today = get_concepts_due_today(user_id=user_id)

    if not all_concepts:
        return {
            "response": (
                "Tu base de conocimiento está vacía. "
                "Empieza capturando algunos términos en el chat y vuelve aquí."
            ),
            "all_concepts": [],
        }

    if not due_today:
        return {
            "response": (
                "¡Estás al día! SM-2 no tiene conceptos programados para repasar hoy. "
                f"Tienes {len(all_concepts)} concepto(s) en tu base de conocimiento. "
                "Sigue capturando nuevos términos para seguir creciendo."
            ),
            "all_concepts": all_concepts,
        }

    total = len(due_today)
    selected = due_today[:MAX_REVIEW_CONCEPTS]

    lines = [
        f"SM-2 tiene {total} concepto(s) programado(s) para repasar hoy:\n",
    ]
    for c in selected:
        stars = _mastery_stars(c.mastery_level)
        excerpt = c.explanation[:120] + "..." if len(c.explanation) > 120 else c.explanation
        cat = f" ({c.category})" if c.category else ""
        interval_txt = f"{int(c.sm2_interval)}d" if c.sm2_interval else "?"
        lines.append(f"• **{c.term}**{cat} — dominio: {stars} | intervalo SM-2: {interval_txt}")
        if excerpt:
            lines.append(f"  _{excerpt}_")
        lines.append("")

    if total > MAX_REVIEW_CONCEPTS:
        lines.append(f"_(y {total - MAX_REVIEW_CONCEPTS} más)_\n")

    lines.append(
        "Podés profundizar preguntándome por aquí sobre cualquier término de la lista, "
        "o practicar con las flashcards cuando uses la app."
    )

    return {
        "response": "\n".join(lines).strip(),
        "all_concepts": all_concepts,
    }
