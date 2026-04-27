# Sprint 30 Close — Examen y certificación por categoría

## Resultado del harness

```
tests/test_sprint30.py: 8 passed, 0 failed
Suite completa tests/: 339 passed, 3 failed (342 tests totales)
```

Los 3 fallos de la suite completa son llamadas reales a Gemini (`tests/test_agents.py` ×2, `tests/test_sprint4.py::test_tutor_uses_bd_context`) cuando la clave o la cuota no permiten respuesta esperada — no son regresiones del código del Sprint 30.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `db/schema.py` | Tablas `certifications` (SQLite: REAL, INTEGER 0/1; PostgreSQL: DOUBLE PRECISION, BOOLEAN, SERIAL) y `exam_sessions` (JSON en TEXT + `current_question`); DDL en `executescript` SQLite, `_init_db_postgresql`, `_run_migrations_sqlite` y `_run_migrations_postgresql` (idempotente `IF NOT EXISTS`). |
| `db/operations.py` | `save_certification`, `get_certifications`, `get_best_score`, `replace_exam_session`, `get_exam_session_for_user`, `update_exam_session_progress`, `delete_exam_session`. |
| `agents/exam_agent.py` | **Nuevo:** `generate_exam` (Gemini, 10 ítems MCQ, progresión fácil/medio/difícil; fallo → `[]`), `evaluate_exam` (umbral 80%). |
| `ui/components.py` | `render_certification_badge(category, score, date)`. |
| `ui/app.py` | Vista Dominar: badge por categoría certificada, botón «Hacer examen», bloque de flujo (`st.radio` + Siguiente), `st.balloons()` y `save_certification` si aprueba; conceptos a reforzar si no aprueba. |
| `bot/handlers.py` | `/examen` y `/examen [categoría]`; `try_handle_exam_answer` en mensajes libres con sesión activa; persistencia vía `exam_sessions`; mención en `/start`. |
| `tests/test_sprint30.py` | **Nuevo:** 8 casos del harness Sprint 30. |

## Decisiones de diseño

### Umbral y persistencia
- Aprobación: **score ≥ 0.8** (8/10). Solo se llama `save_certification(..., passed=True)` al aprobar (Streamlit y Telegram).
- `get_best_score` usa `MAX(score)` sobre todos los intentos de esa categoría.

### Telegram
- Una sesión activa por usuario: `replace_exam_session` borra filas previas del mismo `user_id` antes de insertar.
- Respuestas: letras `a`–`d` o dígitos `1`–`4`.

### Agente de examen
- Tras parseo, solo se aceptan exactamente **10** preguntas bien formadas; la progresión de dificultad se fuerza por índice para coherencia con la especificación.

## Estado del proyecto

- Dominar y Telegram permiten examen por categoría con certificación persistida y badge en la UI.
- Tabla `exam_sessions` soporta el flujo conversacional del bot entre mensajes.
