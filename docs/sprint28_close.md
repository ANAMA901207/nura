# Sprint 28 Close — Árbol jerárquico conceptual

## Resultado del harness

```
7 passed, 0 failed, 0 regressions
39 passed total (sprints 23–28)
```

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `db/schema.py` | Tabla `concept_hierarchy` añadida a `_init_db_sqlite` (executescript), `_init_db_postgresql` y a ambas funciones de migración (`_run_migrations_sqlite`, `_run_migrations_postgresql`) — idempotente con `CREATE TABLE IF NOT EXISTS` |
| `db/operations.py` | 3 funciones nuevas: `save_hierarchy(user_id, child_id, parent_id, relation_type)`, `get_hierarchy(user_id) -> list[dict]` (con JOIN a conceptos para incluir terms), `get_concept_tree(user_id, category=None) -> dict` (árbol anidado recursivo) |
| `agents/hierarchy_agent.py` | **Nuevo archivo.** `detect_hierarchy(new_concept, existing_concepts, user_profile) -> list[dict]`: llama a Gemini con prompt de análisis jerárquico, valida IDs y tipos de relación, retorna `[]` ante cualquier error |
| `agents/capture_agent.py` | Post-captura: bloque `try/except` que llama a `detect_hierarchy` con el nuevo concepto y los últimos 20 existentes; guarda relaciones con `save_hierarchy`. La captura nunca se bloquea si el agente falla |
| `ui/components.py` | `render_tree(tree_dict, depth=0)`: renderiza árbol anidado con `st.expander` recursivos; muestra tipo de relación junto a cada nodo; maneja árbol vacío con `st.info` |
| `ui/app.py` | Toggle radio `🔗 Mapa de conexiones / 🌳 Árbol jerárquico` en `_render_view_conectar`; si árbol seleccionado: llama `get_concept_tree` y `render_tree`; importado `render_tree` en cabecera |
| `bot/handlers.py` | `handle_arbol(telegram_id, user_id, category=None) -> str`: genera árbol ASCII con `├──`, `└──`, `│`; ruta `/arbol [categoría]` en `process_update` |
| `tests/test_sprint28.py` | **Nuevo archivo.** 7 casos con fixture `tmp_db` aislada; LLM siempre mockeado vía `patch("langchain_google_genai.ChatGoogleGenerativeAI")` |

## Decisiones de diseño

### Tabla `concept_hierarchy` separada de `connections`
La tabla `connections` modela relaciones semánticas arbitrarias (A↔B con etiqueta libre).
La tabla `concept_hierarchy` modela jerarquía estricta (hijo → padre con tipos normalizados).
Mantenerlas separadas evita contaminar el mapa de conexiones existente y permite
queries específicas de árbol sin ambigüedad.

### `detect_hierarchy` nunca bloquea la captura
Toda la invocación del agente en `capture_agent.py` está envuelta en `try/except`.
Si Gemini falla, si el JSON es inválido, si los IDs no existen en la BD:
el concepto ya fue guardado y el usuario recibe su respuesta normalmente.

### `get_concept_tree` — construcción recursiva en Python
En lugar de una CTE recursiva (que requeriría SQL distinto para SQLite y PostgreSQL),
se usa `get_hierarchy()` para traer todas las relaciones y se construye el árbol en Python.
Esto mantiene la capa SQL simple e idéntica en ambos motores.

### Mock de LLM via `langchain_google_genai`
`ChatGoogleGenerativeAI` se importa dentro de `detect_hierarchy` (lazy import).
Para parchearlo en los tests se usa `patch("langchain_google_genai.ChatGoogleGenerativeAI")`,
que reemplaza la clase en su módulo de origen antes de que el import lazy la resuelva.

## Estado del proyecto

- **Árbol jerárquico** completamente implementado: detección automática al capturar,
  visualización en Streamlit (toggle árbol/mapa) y consulta desde Telegram (`/arbol`).
- **Bot de Telegram** (Sprints 25–28): 10 comandos activos —
  `/start`, `/capturar`, `/repasar`, `/streak`, `/meta`, `/vincular`,
  `/recordatorio`, `/podcast`, `/audio`, `/arbol`.
- **Suite de tests**: 39 passed (sprints 23–28), 0 regressions.
