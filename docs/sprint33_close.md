# Sprint 33 Close — Tools formales LangGraph (tutor)

## Resultado del harness

```
tests/test_sprint33.py: 8 passed, 0 failed
Suite completa tests/: 360 passed, 3 failed (363 tests)
```

Los 3 fallos corresponden a entorno / API de Gemini (mensaje de conexión o respuestas que no cumplen aserciones de contenido): `tests/test_agents.py` (2) y `tests/test_sprint4.py::test_tutor_uses_bd_context`. No están ligados a la lógica nueva de tools del tutor; con `GOOGLE_API_KEY` válida y servicio disponible suelen pasar.

## Archivos tocados (Sprint 33)

| Archivo | Cambio |
|---------|--------|
| `tools/__init__.py` | Paquete `tools` (vacío, según spec). |
| `tools/web_search_tool.py` | `@tool web_search` → delega en `tools.search_tool.web_search`, retorna JSON string. |
| `tools/diagram_tool.py` | `@tool generate_diagram(concept, relationships)` → `generate_diagram_svg` (tipo `flow`). |
| `tools/hierarchy_tool.py` | `@tool lookup_hierarchy` → `get_concept_tree` en `db.operations`. |
| `tools/concept_lookup_tool.py` | `@tool lookup_concepts` → `get_all_concepts` + `find_similar_concepts_for_tool` / `build_similar_concepts_prompt_section` en `tutor_agent` (import dinámico para evitar ciclos). |
| `tools/tutor_graph_tools.py` | `TUTOR_BIND_TOOLS`: lista ordenada para `bind_tools`. |
| `agents/tutor_agent.py` | `llm_tutor.bind_tools(TUTOR_BIND_TOOLS)` + bucle interno `invoke` → `ToolMessage` cuando hay `tool_calls`; inyección de `user_id` en hierarchy/concept lookup; merge de resultados de `web_search` en `sources`; conserva clasificación `needs_search` + `web_search` directo y `_NURA_TOOLS` importado para compatibilidad Sprint 19 / ToolNode. |
| `tests/test_sprint33.py` | **Nuevo:** 8 casos (carpeta tools, cuatro tools con `name`, descripciones, `TUTOR_BIND_TOOLS`, `build_graph()`). |
| `docs/sprint33_close.md` | Este cierre. |

## Decisiones de diseño

- **Flujo tutor → tools → tutor:** implementado **dentro** de `tutor_agent` (bucle de mensajes con `ToolMessage`), no como aristas condicionales nuevas en `agents/graph.py`, para no alterar el grafo global ni el contrato del estado. El nodo `tools` del grafo sigue existiendo con `NURA_TOOLS` (Sprint 19).
- **`_NURA_TOOLS` en `tutor_agent`:** se mantiene la importación de `NURA_TOOLS` como `_NURA_TOOLS` para que `tests/test_sprint19.py` y el ToolNode del grafo sigan alineados con la intención original de introspección.
- **Doble vía web:** el paso explícito `needs_search` + contexto en el prompt humano se conserva; el modelo además puede invocar la tool `web_search` si lo decide, con deduplicación razonable en `sources` vía JSON parseado.

## Estado del proyecto

El tutor expone cuatro tools LangChain formales, enlazadas con `bind_tools`, con ejecución determinista en código cuando el LLM emite `tool_calls`. El harness del Sprint 33 valida estructura y que `build_graph()` compila sin error.
