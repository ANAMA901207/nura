"""
tools/hierarchy_tool.py
=======================
Tool LangChain para consultar el árbol jerárquico del usuario (Sprint 33).
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from db.operations import get_concept_tree


@tool
def lookup_hierarchy(user_id: int, concept: str) -> str:
    """Consulta el árbol jerárquico del usuario para
    encontrar dónde encaja un concepto y qué conceptos
    padre e hijos tiene. Úsala para contextualizar
    explicaciones con la estructura mental del usuario."""
    tree = get_concept_tree(user_id)
    if not tree:
        return json.dumps(
            {"message": "No hay jerarquía registrada aún.", "concept": concept},
            ensure_ascii=False,
        )
    # Árbol completo (acotado en tamaño para el contexto del modelo)
    raw = json.dumps(tree, ensure_ascii=False)
    if len(raw) > 12000:
        raw = raw[:12000] + "…"
    return json.dumps(
        {"concept_query": concept, "tree_json": raw},
        ensure_ascii=False,
    )
