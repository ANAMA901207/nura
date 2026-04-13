# Sprint 18 Close — Tutor detecta conceptos nuevos y sugiere agregarlos

## Objetivo
Al responder una pregunta, el tutor detecta automáticamente términos técnicos mencionados en su respuesta que el usuario aún no tiene en su mapa de conocimiento, y los presenta como sugerencias de captura con un banner interactivo.

## Archivos creados
| Archivo | Descripción |
|---|---|
| `tools/concept_detector_tool.py` | `detect_new_concepts(response_text, existing_terms, user_id)` — extrae sustantivos técnicos via Gemini, filtra los ya existentes (case-insensitive), devuelve máximo 5. Retorna `[]` ante cualquier fallo. |
| `tests/test_sprint18.py` | 20 tests en 6 clases cubriendo tipo de retorno, filtrado, límite de 5, fallos de API, integración con `tutor_agent` y regla de 4 palabras. |

## Archivos modificados
| Archivo | Cambio |
|---|---|
| `agents/state.py` | Campo `suggested_concepts: list[str]` añadido a `NuraState` con docstring. |
| `agents/tutor_agent.py` | Paso 6 post-respuesta: llama a `detect_new_concepts(tutor_response, existing_terms, user_id)`. Resultado en `state["suggested_concepts"]`. Envuelto en `try/except`. |
| `ui/app.py` | Banner sutil en el bloque `else` de la vista Descubrir (modo `question`): checkboxes por término sugerido + botón "Agregar seleccionados". Al confirmar llama a `_handle_submit` con `user_context='[CLARIFIED]: concepto técnico detectado en respuesta del tutor'`. Key `_sc_done_{hist_idx}` evita repetir el banner una vez procesado. |

## Implementación destacada

### `tools/concept_detector_tool.py`
- Guard de texto mínimo (20 chars) antes de llamar a Gemini — evita llamadas innecesarias.
- Filtrado case-insensitive: `existing_lower = {t.lower() for t in existing_terms}`.
- Regla de 4 palabras: `if len(clean.split()) > 4: continue`.
- Corta en 5 con `if len(filtered) >= 5: break`.

### `ui/app.py` — banner de sugerencias
- `_sc_key = f"_sc_done_{hist_idx}"` — impide que el banner reaparezca tras agregar conceptos.
- `_sc_checked_key = f"_sc_checks_{hist_idx}"` — mantiene el estado de cada checkbox independientemente por entrada del historial.
- El botón "Agregar seleccionados" itera solo los conceptos marcados y llama `_handle_submit` con el contexto especial `[CLARIFIED]:` para evitar el loop de ambigüedad.

## Resultado del harness
```
201 passed, 17 warnings, 7 subtests passed in 183.94s (0:03:03)
```
20 tests nuevos de Sprint 18. 0 regresiones.
