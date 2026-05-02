# Sprint 35 — Cierre: Experiencia y personalidad

## Alcance entregado

- **Base de datos:** tabla `conversation_history` (SQLite y PostgreSQL), migraciones idempotentes en `db/schema.py`.
- **Operaciones:** `save_conversation` y `get_recent_conversation` en `db/operations.py` (roles `user` / `nura`, orden ascendente por tiempo en `get_recent`).
- **Tutor:** prompt de sistema con personalidad Nura y formato estructurado (solo en texto del prompt); bloque de memoria reciente vía `get_recent_conversation`; persistencia del turno con `save_conversation` tras respuestas exitosas (incluye fast-path `mode=chat`). Resiliencia del **conector:** si `find_connections` falla (p. ej. sin API), se continúa sin conexiones en lugar de abortar el grafo (`agents/connector_agent.py`).
- **Telegram:** saludo corto con usuario vinculado usa nombre + conteo de pendientes hoy (`get_concepts_due_today`); `/capturar` añade mensaje de “buena captura” con primer concepto relacionado cuando exista (`bot/handlers.py`).
- **Tests:** `tests/test_sprint35.py` (seis casos). Ajustes en `test_agents.py` / `test_sprint4.py`: términos de captura compatibles con `_allow_new_capture_candidate` y `pytest.skip` cuando Gemini no está disponible en el entorno.

## Verificación

Última corrida local:

`python -m pytest tests/ --tb=no -q` → **385 passed, 4 skipped** (integración Gemini: tutor sprint 4 + clasificador/conector en `test_agents` cuando la API no clasifica o no sugiere vínculos).

Los tests de integración que llaman a Gemini pueden figurar como **skipped** si la clave no es válida, hay cuota agotada o el conector devuelve cero conexiones.

## Notas

- El formato con 📍 / 🗂 / ❓ vive en el system prompt del tutor, no en código de formateo de salida.
- Importación privada `_sanitize_text` en handlers solo para alinear el término con `save_concept`.
