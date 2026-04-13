# Sprint 16 — Cierre

## Objetivo
Mensaje motivador híbrido al final de sesión: combina lógica determinista
de clasificación de eventos con generación LLM (Gemini) para producir un
mensaje corto, cercano y específico basado en los datos reales del usuario.
Si Gemini falla, usa mensajes de respaldo predefinidos.

## Archivos creados
| Archivo | Descripción |
|---|---|
| `agents/motivator_agent.py` | Nuevo agente con lógica determinista + llamada Gemini |
| `tests/test_sprint16.py` | Harness con 14 tests (7 casos + 7 subtests) |

## Archivos modificados
| Archivo | Cambio |
|---|---|
| `db/operations.py` | Añadida función `get_session_stats(user_id) -> dict` |
| `ui/components.py` | Añadida función `render_motivational_banner(message) -> None` |
| `ui/app.py` | Banner integrado en `_render_session_summary()` y en bloque quiz |

## Detalles de implementación

### `db/operations.py` — `get_session_stats`
Retorna 6 campos:
- `conceptos_hoy`, `conexiones_hoy`, `repasados_hoy` — del `DailySummary` del día.
- `racha` — días consecutivos activos (vía `get_streak`).
- `es_primera_sesion` — `True` si `total_conceptos <= conceptos_hoy` y `conceptos_hoy > 0`.
- `quiz_score` — siempre `None`; el llamador lo inyecta externamente.

### `agents/motivator_agent.py`
**Tipos de evento (prioridad descendente):**
`primera_sesion` → `racha_7` → `conexiones_3` → `conceptos_5` → `solo_repaso` → `quiz_bajo` → `default`

**Flujo:**
1. `get_session_stats(user_id)` + inyección de `quiz_score`.
2. `_determine_event_type(stats)` → tipo determinista.
3. `_gemini_message(tipo, stats)` → LLM con prompt de constelaciones/nodos.
4. Si falla → `_fallback_message(tipo)` → mensaje predefinido garantizado.

### `ui/components.py` — `render_motivational_banner`
Banner sutil con fondo `#1e1e2e`, borde superior `#45475a`, ícono estrella
Lucide 16 px, texto en `#a6adc8` itálico. El mensaje se escapa con
`html.escape()` antes de embeberlo.

### `ui/app.py`
- **`_render_session_summary()`**: banner después del botón "Nueva sesión".
- **Bloque quiz (historial)**: banner tras guardar resultados, pasando `quiz_score=float(_pct_q)`.
- Ambos puntos usan `try/except` para no bloquear el flujo principal.

## Resultado del harness
```
160 passed, 17 warnings, 7 subtests passed in 89.86s (0:01:29)
```
**160/160 tests pasados — 0 regresiones.**
