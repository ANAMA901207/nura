# Sprint 33 — Tools formales LangGraph

## Objetivo
Migrar las capacidades del tutor a tools formales
de LangGraph — en lugar de llamadas directas embebidas
en el agente. Esto hace el sistema más robusto,
testeable y extensible.

## El problema que resuelve
Hoy las tools (web search, diagramas SVG, jerarquía)
están acopladas dentro del tutor_agent como llamadas
directas. Un agente real de LangGraph debería poder
decidir autónomamente cuándo usar cada tool.

## Cambios de arquitectura
Antes:
  tutor_agent.py → llama directamente a web_search()
  tutor_agent.py → llama directamente a generate_svg()

Después:
  tutor_agent.py → LangGraph decide qué tool usar
  tools/web_search_tool.py → @tool decorator
  tools/diagram_tool.py → @tool decorator
  tools/hierarchy_tool.py → @tool decorator
  tools/concept_lookup_tool.py → @tool decorator

## Tools a formalizar
1. **web_search_tool** — busca en la web cuando el
   tutor necesita información actualizada
2. **diagram_tool** — genera diagramas SVG cuando
   el concepto se beneficia de una visualización
3. **hierarchy_tool** — consulta el árbol jerárquico
   del usuario para contextualizar explicaciones
4. **concept_lookup_tool** — busca conceptos similares
   en el mapa del usuario

## Archivos a crear/modificar
- `tools/` — nueva carpeta
- `tools/__init__.py`
- `tools/web_search_tool.py` — @tool web_search
- `tools/diagram_tool.py` — @tool generate_diagram
- `tools/hierarchy_tool.py` — @tool lookup_hierarchy
- `tools/concept_lookup_tool.py` — @tool lookup_concepts
- `agents/tutor_agent.py` — refactor para usar
  tools formales con bind_tools de LangGraph
- `tests/test_sprint33.py` — harness

## Harness
- `test_web_search_tool_is_tool` — tiene @tool decorator
- `test_diagram_tool_is_tool`
- `test_hierarchy_tool_is_tool`
- `test_concept_lookup_tool_is_tool`
- `test_tutor_has_tools_bound` — tutor tiene tools
- `test_tools_folder_exists`
- `test_all_tools_have_docstring` — cada tool tiene
  descripción para que el LLM sepa cuándo usarla

## Reglas
- El comportamiento del tutor NO debe cambiar
  para el usuario — solo la arquitectura interna
- Todos los tests existentes deben seguir pasando
- Correr pytest al cerrar y crear sprint33_close.md