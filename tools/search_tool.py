"""
tools/search_tool.py
====================
Herramienta de busqueda web para el tutor de Nura.

Proporciona una funcion unica web_search() que consulta DuckDuckGo sin
necesidad de API key ni cuenta.  Se usa desde tutor_agent cuando la
pregunta del usuario requiere informacion actualizada (versiones, eventos
recientes, comparaciones de herramientas, precios).

Implementacion
--------------
Usa la libreria `ddgs` (DuckDuckGo Search) que accede al motor de
busqueda de DuckDuckGo de forma anonima y sin limite de cuota diaria.
Es la alternativa libre a la Custom Search JSON API de Google.

Instalacion de la dependencia:
    pip install ddgs
"""

from __future__ import annotations

from ddgs import DDGS

# Numero maximo de resultados que se solicitan al buscador por defecto
_DEFAULT_MAX_RESULTS = 5


def web_search(query: str, max_results: int = _DEFAULT_MAX_RESULTS) -> dict:
    """
    Realiza una busqueda web con DuckDuckGo y devuelve los resultados.

    Cada resultado incluye titulo, URL y snippet del contenido de la pagina.
    Si la busqueda falla por cualquier razon (red, timeout, rate limit),
    la funcion captura la excepcion y devuelve un dict con results vacio y
    el mensaje de error en el campo "error", sin propagar la excepcion.

    Parametros
    ----------
    query       : Termino o pregunta a buscar en la web.
    max_results : Numero maximo de resultados a devolver (defecto 5).

    Devuelve
    --------
    dict con dos posibles formas:
        Exito:  {"results": [{"title": str, "url": str, "snippet": str}, ...]}
        Error:  {"results": [], "error": str}

    Ejemplo
    -------
    >>> result = web_search("que version de LangChain es la mas reciente?")
    >>> for r in result["results"]:
    ...     print(r["title"], r["url"])
    """
    try:
        raw_results: list[dict] = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                raw_results.append(item)

        results = [
            {
                "title":   item.get("title", ""),
                "url":     item.get("href", ""),
                "snippet": item.get("body", ""),
            }
            for item in raw_results
        ]
        return {"results": results}

    except Exception as exc:
        return {"results": [], "error": str(exc)}


# ── Sprint 19: tool formal ────────────────────────────────────────────────────

from langchain_core.tools import tool as _lc_tool  # noqa: E402
import json as _json  # noqa: E402


@_lc_tool
def search_web_tool(query: str, max_results: int = 5) -> str:
    """
    Search the web with DuckDuckGo and return current results.

    Use this when the user asks about recent events, tool versions,
    price comparisons, or any information that may have changed recently.
    Returns a JSON string with a 'results' array (title, url, snippet)
    or an 'error' key if the search fails.

    Parameters
    ----------
    query       : The search query.
    max_results : Maximum number of results to return (default 5).
    """
    result = web_search(query, max_results)
    return _json.dumps(result)
