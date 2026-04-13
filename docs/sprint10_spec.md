# Sprint 10 — Tutor con web search

## Objetivo
El tutor busca en web antes de responder preguntas,
dando información actualizada y con fuentes.

## Funcionalidades
1. Tutor detecta si la pregunta necesita info actualizada
2. Si sí → busca en web antes de responder
3. Respuesta incluye fuentes al final
4. Si no → responde solo con contexto de BD (como antes)
5. Indicador visual "🌐 Buscando en web..." durante la búsqueda

## Cuándo buscar en web
- Preguntas sobre herramientas específicas ("qué versión de...")
- Preguntas sobre eventos recientes ("qué pasó con...")
- Preguntas comparativas ("cuál es mejor X o Y")
- Preguntas de precio/disponibilidad

## Cuándo NO buscar
- Preguntas sobre conceptos ya guardados en BD
- Preguntas conceptuales generales
- Preguntas de repaso

## Harness
- Pregunta sobre herramienta activa dispara web search
- Pregunta conceptual simple no dispara web search
- Respuesta con web search incluye campo fuentes
- Fallo de web search no rompe el tutor (fallback a BD)
- Indicador de fuente aparece en la respuesta