# Sprint 19 — Tools formales LangGraph

## Objetivo
Convertir las funciones directas en tools registradas
con @tool decorator para que el LLM pueda decidir
dinámicamente cuándo y cómo invocarlas.

## Qué cambia
Actualmente los agentes llaman funciones directamente:
  save_concept(term, context)

Con tools formales el LLM decide:
  "necesito guardar este concepto" → invoca tool

## Tools a crear
1. `save_concept_tool` — guarda concepto en BD
2. `classify_concept_tool` — clasifica con Gemini
3. `find_connections_tool` — detecta conexiones
4. `search_web_tool` — busca en DuckDuckGo
5. `get_concepts_tool` — lee conceptos del usuario
6. `update_mastery_tool` — actualiza nivel de dominio

## Arquitectura
- Tools registradas con @tool de LangChain
- ToolNode de LangGraph para ejecutarlas
- Agentes usan bind_tools() para tener acceso
- Flujo: agent → decide tool → ToolNode → agent

## Beneficio
Nura pasa de agentic workflow a true multi-agent
system — el LLM orquesta las tools dinámicamente

## Harness
- Cada tool registrada es invocable correctamente
- ToolNode ejecuta tools sin errores
- Agente selecciona la tool correcta para cada input
- Regresión cero en tests existentes
- Flujo end-to-end funciona igual que antes