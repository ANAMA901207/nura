"""
tools/concept_lookup_tool.py
============================
Tool LangChain para buscar conceptos relacionados en el mapa del usuario (Sprint 33).
"""

from __future__ import annotations

import importlib
import json

from langchain_core.tools import tool

from db.operations import get_all_concepts


@tool
def lookup_concepts(user_id: int, query: str) -> str:
    """Busca conceptos similares en el mapa de
    conocimiento del usuario. Úsala para conectar
    explicaciones nuevas con lo que el usuario
    ya sabe. Retorna lista de conceptos relacionados."""
    concepts = get_all_concepts(user_id=user_id)
    if not concepts or not (query or "").strip():
        return json.dumps({"matches": [], "note": "sin datos"}, ensure_ascii=False)

    ta = importlib.import_module("agents.tutor_agent")
    matches = ta.find_similar_concepts_for_tool(query, concepts, limit=12)
    block = ta.build_similar_concepts_prompt_section(query, concepts)
    return json.dumps(
        {"matches": matches, "prompt_block": block or ""},
        ensure_ascii=False,
    )
