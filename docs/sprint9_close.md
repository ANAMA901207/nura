# Sprint 9 — Quiz + Perfil Adaptativo (Cerrado)

## Resultado: 5/5 tests pasados

## Que se construyo

### db/operations.py
- `get_mastery_by_category() -> dict[str, float]`: promedio de mastery_level por categoria (solo conceptos clasificados)
- `get_streak() -> int`: dias consecutivos con actividad en daily_summaries (concepts_captured > 0 o concepts_reviewed > 0)
- `get_dominated_concepts() -> list[Concept]`: conceptos con mastery_level >= 4, ordenados por nivel

### agents/state.py
- Nuevo campo `quiz_questions: list[dict]` en NuraState
- Modo `'quiz'` documentado en el docstring de NuraState

### agents/capture_agent.py
- Nuevas constantes `_QUIZ_WORDS` y `_QUIZ_PHRASES` para detectar solicitudes de quiz
- Nueva funcion `_is_quiz(text)` con logica de frases + palabras clave
- Prioridad 1 en capture_agent: si _is_quiz → mode='quiz' (antes que 'review' y 'question')
- Todos los returns incluyen `quiz_questions: []` para compatibilidad con NuraState

### agents/quiz_agent.py (nuevo)
- Selecciona aleatoriamente hasta 5 conceptos clasificados con flashcard
- Llama a Gemini con prompt estricto para JSON de preguntas de opcion multiple
- Parsea y valida cada pregunta (campos requeridos, 4 opciones, correct_index 0-3)
- Devuelve `quiz_questions` y mensaje de confirmacion en state
- Incluye retry con backoff para rate limits

### agents/graph.py
- Nuevo nodo `quiz` → quiz_agent
- `_route_after_capture`: ruta `mode='quiz'` → `"quiz"`
- `add_conditional_edges` incluye `"quiz": "quiz"`
- `add_edge("quiz", END)`

### ui/components.py
- Nueva funcion `render_quiz(questions: list[dict]) -> dict`:
  - Muestra todas las preguntas con radio buttons (st.radio)
  - Boton "Responder" revela respuestas correctas/incorrectas con iconos + explicacion
  - Muestra puntaje con codigo de color (verde/amarillo/rojo segun %
  - Boton "Guardar resultados" llama a record_flashcard_result por cada concepto y devuelve {concept_id: bool}
  - Usa session_state con fingerprint del quiz para resetear estado al cambiar de quiz

### ui/app.py
- Imports: `get_concepts_due_today`, `get_dominated_concepts`, `get_mastery_by_category`, `get_streak`, `render_quiz`
- `_empty_state`: incluye `quiz_questions: []`
- `_BADGES`: nuevo badge `"quiz": ("#f9e2af", "Quiz")`
- Historial Tab 1: rama `elif mode == "quiz"` llama a `render_quiz(result["quiz_questions"])`
- Botones de accion rapida: columnas con "Sesion de repaso" y "Quiz" (nuevo)
- Nueva funcion `_render_learning_profile()`:
  - Metricas: racha activa, conceptos dominados
  - Grafico de barras `st.bar_chart` con % de dominio por categoria
  - Badges "Mas fuerte en: X" y "Necesita refuerzo: Y"
- `_render_tab_app()`: llama a `_render_learning_profile()` antes del resumen diario

### tests/test_sprint9.py
- 5 verificaciones:
  1. quiz_agent con API real genera preguntas con campos requeridos (SKIP si cuota agotada)
  2. Preguntas tienen exactamente 4 opciones (mock de ChatGoogleGenerativeAI)
  3. get_mastery_by_category calcula promedios correctos por categoria
  4. get_streak devuelve 0 con BD vacia
  5. capture_agent detecta mode='quiz' con 'ponme a prueba' y otras frases clave
