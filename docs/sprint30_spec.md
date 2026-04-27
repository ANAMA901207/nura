# Sprint 30 — Examen y certificación por categoría

## Objetivo
Darle peso real al "dominar" — el usuario demuestra
que domina una categoría pasando un examen generado
por Nura, no solo acumulando flashcards.

## El problema que resuelve
Hoy el sistema dice que "dominaste" algo basado en
aciertos en flashcards. No se siente riguroso.
Un examen real con umbral de aprobación cambia eso.

## Funcionalidades

### 1. Examen por categoría
- El usuario elige una categoría y solicita el examen
- Nura genera 10 preguntas progresivas (fácil → difícil)
- El usuario responde una por una
- Al final → puntaje + feedback por pregunta

### 2. Certificación
- Si pasa el umbral (80%) → categoría marcada como
  "certificada" con fecha
- Si no pasa → Nura dice qué conceptos reforzar
- Una categoría puede tener múltiples intentos
- Solo el mejor puntaje cuenta

### 3. Visualización
- En vista Dominar → badge "✓ Certificada" en
  categorías aprobadas con fecha
- En perfil → lista de certificaciones obtenidas

### 4. Telegram
- `/examen [categoría]` → inicia examen por Telegram
- El bot hace las preguntas una por una
- Al final muestra resultado y si certificó

## Archivos a modificar
- `db/schema.py` — nueva tabla `certifications`:
  (id, user_id, category, score, passed, attempted_at)
- `db/operations.py` — funciones:
  `save_certification(user_id, category, score,
  passed) -> None`
  `get_certifications(user_id) -> list`
  `get_best_score(user_id, category) -> float | None`
- `agents/exam_agent.py` — nuevo agente:
  `generate_exam(category, concepts, user_profile)
  -> list[Question]`
  `evaluate_answer(question, answer, concept) -> dict`
- `ui/app.py` — en vista Dominar:
  botón "Hacer examen" por categoría
  flujo de preguntas con st.radio
  resultado final con badge si certifica
- `ui/components.py` — `render_certification_badge`
- `bot/handlers.py` — `/examen [categoría]`
  con flujo conversacional de preguntas

## Harness
- `test_certifications_table_exists`
- `test_save_and_get_certification`
- `test_get_best_score`
- `test_exam_agent_generates_10_questions`
- `test_exam_agent_questions_have_options`
- `test_passed_when_score_above_threshold`
- `test_failed_when_score_below_threshold`
- `test_examen_command_telegram`

## Reglas
- Umbral de aprobación: 80% (8/10 preguntas)
- No romper tests existentes
- Correr pytest al cerrar y crear sprint30_close.md