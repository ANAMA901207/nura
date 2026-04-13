# Sprint 4 — Tutor Agent + integración final

## Objetivo
Completar Nura con el agente tutor que responde preguntas,
modo repaso nocturno, y pulida final para demo.

## Funcionalidades
1. Tutor Agent — responde preguntas en modo conversacional
   usando el conocimiento ya guardado en BD como contexto
2. Fix placeholder — eliminar mensaje "Sprint 3 lo procesará pronto"
3. Sesión de repaso — el tutor sugiere conceptos para repasar
   basado en mastery_level bajo o última revisión hace más de 3 días
4. Pulida visual — acentos tildes, spacing, demo-ready

## Harness
- Pregunta recibe respuesta real del tutor (no placeholder)
- Tutor usa conceptos de BD como contexto
- Sesión de repaso sugiere al menos 1 concepto con mastery < 3
- app.py corre sin errores con BD vacía