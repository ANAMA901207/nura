# Sprint 9 — Quiz + Perfil adaptativo

## Objetivo
Modo quiz para medir dominio real con preguntas generadas
por el tutor, y perfil adaptativo que muestra fortalezas
y debilidades por categoría.

## Funcionalidades

### Modo Quiz
- El tutor genera 3-5 preguntas sobre conceptos del usuario
- Preguntas de opción múltiple (4 opciones) generadas por Gemini
- Usuario selecciona respuesta → tutor evalúa y explica
- Al final: puntaje, conceptos fuertes, conceptos a reforzar
- Resultado actualiza mastery_level via record_flashcard_result

### Perfil adaptativo
- Tab 2 nueva sección "Mi perfil de aprendizaje"
- Gráfico de barras por categoría: % de dominio promedio
- Badge "Más fuerte en: X" y "Necesita refuerzo: Y"
- Racha de días activos (streak)
- Total de conceptos dominados (mastery >= 4)

## Harness
- Quiz genera preguntas con 4 opciones válidas
- Respuesta correcta sube mastery del concepto
- Respuesta incorrecta baja mastery del concepto
- Perfil calcula % de dominio por categoría correctamente
- Streak se incrementa si el usuario capturó algo hoy