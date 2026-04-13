# Sprint 19 Close — Tools formales LangGraph

## Objetivo
Convertir las funciones directas de herramientas en tools registradas con el decorator `@tool` de LangChain, registrar un `ToolNode` en el grafo y hacer que los agentes estén listos para orquestación dinámica via `bind_tools()`.

## Archivos creados
| Archivo | Descripción |
|---|---|
| `tools/db_tools.py` | 3 tools formales de BD (`save_concept_tool`, `get_concepts_tool`, `update_mastery_tool`) + lista centralizada `NURA_TOOLS` (6 tools). |
| `tests/test_sprint19.py` | 32 tests en 7 clases cubriendo registro, ToolNode, retorno JSON, bind_tools e interfaces originales. |

## Archivos modificados
| Archivo | Cambio |
|---|---|
| `tools/classifier_tool.py` | Añade `classify_concept_tool` con `@tool`. `classify_concept` original intacta. |
| `tools/connector_tool.py` | Añade `find_connections_tool` con `@tool`. `find_connections` original intacta. Importa `get_concept_by_id` y `get_all_concepts` a nivel de módulo (patcheable en tests). |
| `tools/search_tool.py` | Añade `search_web_tool` con `@tool`. `web_search` original intacta. |
| `agents/graph.py` | Importa `ToolNode` y `NURA_TOOLS`. Registra nodo `"tools"` en el `StateGraph`. |
| `agents/tutor_agent.py` | Importa `_NURA_TOOLS`. Aplica `llm_tutor.bind_tools(_NURA_TOOLS)` en la llamada de respuesta libre (no en el clasificador JSON). |
| `agents/capture_agent.py` | Importa `_NURA_TOOLS` con try/except para compatibilidad. |
| `agents/classifier_agent.py` | Importa `_NURA_TOOLS` con try/except para compatibilidad. |
| `agents/connector_agent.py` | Importa `_NURA_TOOLS` con try/except para compatibilidad. |

## Arquitectura de tools

```
NURA_TOOLS (6 tools)
├── save_concept_tool      → db.operations.save_concept
├── get_concepts_tool      → db.operations.get_all_concepts
├── update_mastery_tool    → db.operations.record_flashcard_result
├── classify_concept_tool  → tools.classifier_tool.classify_concept
├── find_connections_tool  → tools.connector_tool.find_connections
└── search_web_tool        → tools.search_tool.web_search

agents/graph.py
└── ToolNode("tools", NURA_TOOLS)  ← registrado, sin routing activo aún
```

## Decisiones de diseño

- **Backward compatibility total**: todas las funciones originales (`classify_concept`, `find_connections`, `web_search`) mantienen su firma y tipo de retorno exactos. Los tools son wrappers que devuelven JSON string.
- **Imports a nivel de módulo**: `save_concept`, `get_all_concepts`, `record_flashcard_result`, `get_concept_by_id` se importan en el nivel del módulo de sus respectivos tool files para que los tests puedan patchearlos con `unittest.mock.patch`.
- **bind_tools() seguro**: se aplica solo al `llm_tutor` (respuesta libre), NO al `llm` de clasificación (que espera JSON estructurado). Esto evita que Gemini genere `tool_calls` en lugar de JSON cuando se necesita una respuesta estructurada.
- **ToolNode sin routing activo**: el nodo existe en el grafo pero ninguna arista apunta hacia él. El flujo actual sigue siendo determinista. El nodo está listo para activarse en una fase de orquestación dinámica futura.

## Resultado del harness
```
233 passed, 17 warnings, 7 subtests passed in 138.87s (0:02:18)
```
32 tests nuevos de Sprint 19. 0 regresiones.
