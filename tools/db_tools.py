"""
tools/db_tools.py
=================
Tools formales de base de datos para Nura — Sprint 19.

Expone las operaciones de BD más frecuentes como herramientas LangChain
(@tool) para que el LLM pueda invocarlas dinámicamente a través de
ToolNode cuando opera en modo agéntico.

Cada tool:
- Lleva un docstring descriptivo que el LLM usa para decidir cuándo
  invocarla.
- Acepta solo tipos primitivos (str, int, bool) para ser serializable
  en el protocolo de herramientas de OpenAI / Gemini.
- Retorna un string JSON con el resultado o {"error": ...} ante fallos.
- Mantiene la separación usuario-datos pasando user_id como argumento.

Las funciones de DB originales (save_concept, get_all_concepts, etc.) no
se modifican — los tools son wrappers delgados encima de ellas.

Al final del archivo se expone NURA_TOOLS: la lista centralizada de todos
los tools formales del proyecto, lista para pasarle a ToolNode o a
llm.bind_tools().
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

# Importaciones al nivel de módulo para que sean patcheables en tests.
from db.operations import (
    get_all_concepts,
    record_flashcard_result,
    save_concept,
)


# ── Tools de base de datos ────────────────────────────────────────────────────

@tool
def save_concept_tool(term: str, context: str = "", user_id: int = 1) -> str:
    """
    Save a new concept to the user's knowledge map.

    Use this when the user mentions a new technical or business term they want
    to learn.  Returns JSON with the saved concept id and term, or an error
    message if the concept already exists or the save fails.

    Parameters
    ----------
    term    : The concept term to save (max 500 chars).
    context : Optional context where the term was encountered.
    user_id : The authenticated user's ID.
    """
    try:
        c = save_concept(term.strip(), context.strip(), user_id=user_id)
        return json.dumps({"id": c.id, "term": c.term, "status": "saved"})
    except Exception as exc:
        return json.dumps({"error": str(exc), "term": term})


@tool
def get_concepts_tool(user_id: int = 1) -> str:
    """
    Get all concepts in the user's knowledge map.

    Returns a JSON array of objects with id, term, category, and
    mastery_level for each concept the user has captured.  Useful for
    building context before answering questions or finding connections.

    Parameters
    ----------
    user_id : The authenticated user's ID.
    """
    try:
        concepts = get_all_concepts(user_id=user_id)
        return json.dumps([
            {
                "id":           c.id,
                "term":         c.term,
                "category":     c.category or "",
                "mastery_level": c.mastery_level,
            }
            for c in concepts
        ])
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@tool
def update_mastery_tool(concept_id: int, correct: bool, user_id: int = 1) -> str:
    """
    Update the mastery level of a concept after a flashcard review.

    Uses the SM-2 spaced-repetition algorithm: correct=True increases the
    interval and possibly the mastery level; correct=False resets the
    interval.  Returns JSON with the updated mastery_level, or an error.

    Parameters
    ----------
    concept_id : Database ID of the concept to update.
    correct    : True if the user answered the flashcard correctly.
    user_id    : The authenticated user's ID.
    """
    try:
        c = record_flashcard_result(concept_id, correct)
        return json.dumps({
            "id":            c.id,
            "term":          c.term,
            "mastery_level": c.mastery_level,
            "status":        "updated",
        })
    except Exception as exc:
        return json.dumps({"error": str(exc), "concept_id": concept_id})


# ── Lista centralizada de todos los tools formales del proyecto ───────────────
# Se importa aquí (después de definir los tools de BD) para evitar importaciones
# circulares.  graph.py y los agentes importan NURA_TOOLS desde este módulo.

from tools.classifier_tool import classify_concept_tool   # noqa: E402
from tools.connector_tool  import find_connections_tool   # noqa: E402
from tools.search_tool     import search_web_tool         # noqa: E402

NURA_TOOLS = [
    save_concept_tool,
    get_concepts_tool,
    update_mastery_tool,
    classify_concept_tool,
    find_connections_tool,
    search_web_tool,
]
"""
Lista de todos los tools formales registrados en Nura.

Usar con:
    ToolNode(NURA_TOOLS)          — para el nodo de ejecución de tools.
    llm.bind_tools(NURA_TOOLS)    — para que el LLM conozca los tools.
"""
