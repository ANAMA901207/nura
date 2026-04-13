# Sprint 3 — Streamlit UI

## Objetivo
Construir la interfaz completa de Nura: chat de captura 
y app de aprendizaje en dos tabs.

## Tab 1: Chat
- Input de texto para capturar términos o hacer preguntas
- El agente responde con la explicación en 5 capas
- Historial de conversación visible en la sesión
- Indicador de modo (capturado / pregunta respondida)

## Tab 2: App
- Resumen diario: cuántos conceptos, conexiones nuevas
- Categorías: lista de conceptos agrupados por category
- Flashcards: frente/reverso, botón para voltear
- Mapa visual: grafo interactivo con pyvis

## Harness
- Tab 1 renderiza sin errores
- Tab 2 renderiza sin errores  
- El grafo LangGraph recibe input y retorna response
- Flashcard muestra frente y voltea al reverso
- Resumen diario muestra fecha actual