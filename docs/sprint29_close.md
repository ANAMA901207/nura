# Sprint 29 Close — Tutor contextual y «Explícame más simple»

## Resultado del harness

```
Sprint 29: 6 passed, 0 failed
Sprints 23–29 (subconjunto): 45 passed, 0 regressions
Suite completa tests/: 331 passed, 3 failed (requieren API Gemini válida en .env)
```

Los 3 fallos de la suite completa son llamadas reales a Gemini (`test_agents.py` ×2,
`test_sprint4.py::test_tutor_uses_bd_context`) cuando la clave o la cuota no permiten
respuesta temática — no son regresiones del código del Sprint 29.

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `db/schema.py` | `_SPRINT29_USER_MIGRATIONS`: columna `last_tutor_response TEXT`; DDL en PostgreSQL y SQLite (`users`) + migraciones idempotentes |
| `db/models.py` | Campo `last_tutor_response: Optional[str] = None` en `User` |
| `db/operations.py` | `_row_to_user` lee `last_tutor_response`; nuevas `save_last_tutor_response(user_id, text)` y `get_last_tutor_response(user_id) -> str \| None`. **Colateral:** `get_streak` tolera filas `fetchone` sin clave `cnt` (tests con mocks) usando `row[0]` como respaldo |
| `agents/tutor_agent.py` | Heurística `_tokenize_for_similarity` / `_similarity_score`; `build_similar_concepts_prompt_section(question, concepts)` insertada antes del bloque de conocimiento en el mensaje al modelo; `simplify_explanation(text, user_profile)` con Gemini y fallback al texto original; `save_last_tutor_response` tras respuestas exitosas del tutor (modo chat y LLM) |
| `ui/app.py` | En historial Descubrir, para modos `question` y `chat`: botón «🔄 Explícame más simple» y bloque «Versión más simple» usando `st.session_state` por entrada del historial |
| `bot/handlers.py` | Comando `/simple` → `handle_simple`; mensaje si no hay `last_tutor_response` en BD |
| `tests/test_sprint29.py` | **Nuevo.** 6 casos según especificación del sprint |

## Decisiones de diseño

### Similitud pregunta ↔ concepto (sin forzar falsos positivos)
Se puntúa con: solapamiento de tokens entre la pregunta y el término/subcategoría,
y coincidencia de la categoría con la pregunta o sus tokens. Solo entran en el
prompt conceptos con puntuación estrictamente **> 0**. Lista vacía → no se
añade ninguna línea «ya conoces».

### Orden del contexto en el prompt del tutor
Primero el bloque opcional de conceptos similares (mapa contextual), luego la
base de conocimiento existente (`_build_knowledge_context`), luego web si aplica,
y al final la pregunta.

### Persistencia de la última respuesta
Se guarda en `tutor_agent` al finalizar una respuesta del nodo (chat canned o
respuesta LLM exitosa). No se guarda en el `return` de error amigable de API,
para no usar `/simple` sobre mensajes de fallo.

### Telegram `/simple`
Reutiliza `get_user_by_id` para armar `user_profile` y llama a
`simplify_explanation` con el texto persistido.

## Estado del proyecto

- Tutor más contextual con hasta 5 conceptos del mapa alineados con la pregunta.
- Simplificación disponible en Streamlit y con `/simple` en Telegram.
- Suite: 45 tests (sprints 23–29), 0 regresiones detectadas en el subconjunto ejecutado.
