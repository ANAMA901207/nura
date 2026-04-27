"""
tools/web_search_tool.py
========================
Tool LangChain formal para búsqueda web del tutor (Sprint 33).

Delega en `tools.search_tool.web_search` (DuckDuckGo) y serializa el resultado.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from tools.search_tool import web_search as _web_search_impl


@tool
def web_search(query: str) -> str:
    """Busca información actualizada en la web cuando
    el usuario pregunta sobre eventos recientes,
    versiones actuales, o información que puede haber
    cambiado. Retorna un resumen de los resultados."""
    data = _web_search_impl(query)
    return json.dumps(data, ensure_ascii=False)
