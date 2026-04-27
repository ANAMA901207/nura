# Sprint 29 — Tutor contextual + Explícame más simple

## Objetivo
Dos mejoras al tutor que lo hacen más personalizado
y más accesible.

## Funcionalidad 1 — Tutor usa tu mapa al explicar
Antes de explicar un concepto nuevo, el tutor revisa
tu mapa y dice:
"Esto es similar a X que ya tienes" o
"Esto es una extensión de Y que conoces"

### Cómo funciona
- Al recibir una pregunta, el tutor busca en los
  conceptos del usuario los más relacionados
- Si encuentra similitud → abre la explicación
  conectando con lo conocido
- Si no encuentra nada → explica normalmente

## Funcionalidad 2 — Botón "Explícame más simple"
Después de cualquier respuesta del tutor, el usuario
puede pedir una versión más simple.

### En Streamlit
- Botón "🔄 Explícame más simple" debajo de cada
  respuesta del tutor
- El tutor regenera la explicación con lenguaje
  más sencillo y ejemplos cotidianos

### En Telegram
- Comando `/simple` después de cualquier respuesta
- El tutor simplifica su última respuesta

## Archivos a modificar
- `agents/tutor_agent.py` — dos cambios:
  1. Al construir el prompt, incluir los 5 conceptos
     más similares del usuario (por categoría y
     palabras clave)
  2. Nueva función `simplify_explanation(text,
     user_profile) -> str` que reformula más simple
- `ui/app.py` — botón "Explícame más simple" debajo
  de respuestas del tutor en vista Descubrir
- `bot/handlers.py` — comando `/simple` que llama
  a `simplify_explanation` con la última respuesta

## Harness
- `test_tutor_includes_user_context` — prompt
  contiene conceptos del usuario
- `test_tutor_connects_to_known_concept` — si hay
  concepto similar, respuesta lo menciona
- `test_simplify_returns_shorter_text` — versión
  simple es diferente a la original
- `test_simple_command_telegram` — `/simple` →
  llama a simplify_explanation
- `test_simple_button_triggers_regeneration` —
  botón activa regeneración en Streamlit

## Reglas
- Si no hay conceptos similares → tutor explica
  normalmente, sin forzar conexiones falsas
- No romper tests existentes
- Correr pytest al cerrar y crear sprint29_close.md