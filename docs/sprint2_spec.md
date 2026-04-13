# Sprint 2 — Agentes de captura, clasificación y conexión

## Objetivo
Construir los tres agentes core de Nura y conectarlos 
en un grafo LangGraph con tests que verifiquen comportamiento.

## Archivos creados
- `agents/state.py` — NuraState TypedDict
- `agents/capture_agent.py` — detecta término vs pregunta
- `agents/classifier_agent.py` — clasifica y explica con Gemini
- `agents/connector_agent.py` — detecta relaciones entre conceptos
- `agents/graph.py` — StateGraph completo
- `tools/classifier_tool.py` — llama a Gemini para clasificar
- `tools/connector_tool.py` — llama a Gemini para conectar

## Flujo
capture → [mode=='capture'] → classifier → connector → END
        → [mode!='capture'] → END

## Modelo
gemini-2.5-flash via langchain-google-genai
GOOGLE_API_KEY y GEMINI_MODEL leídos de .env

## Harness
5/5 passed
[1] Término nuevo crea Concept en BD
[2] Classifier llena category y flashcard
[3] Dos conceptos relacionados generan Connection
[4] Pregunta no crea Concept nuevo
[5] Primer concepto retorna 0 conexiones