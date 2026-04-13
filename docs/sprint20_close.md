# Sprint 20 — Bugs críticos + personalización (CLOSE)

## Resultado del harness
**258 passed, 1 pre-existing failure (API key), 0 regressions**
_(26 tests nuevos en `tests/test_sprint20.py`)_

---

## Cambios implementados

### 1. Flashcard loop infinito (RESUELTO)
**`ui/app.py` → `_render_flashcard_session`**

- Cuando el usuario responde "No lo sabía" en una flashcard, se verifica si el contador `fc_results[id]["incorrect"]` llega a 3 o más en la sesión.
- Si `incorrect >= 3`: la tarjeta NO vuelve a la cola; se marca `deferred=True` y queda fuera de la sesión actual.
- Si `incorrect < 3`: la tarjeta vuelve al final de la cola (comportamiento anterior).
- Botón **"Terminar sesión"** visible en todo momento durante la sesión (tanto antes como después de voltear la tarjeta), llama directamente a `fc_session_done = True` y `st.rerun()`.

### 2. Botón "Repasar ahora" no hacía nada (RESUELTO)
**`ui/app.py` → `_render_view_dominar`**

- Causa raíz: `due_today` (de `get_concepts_due_today`) podía incluir conceptos sin `flashcard_front`. Al pasar esos IDs a `_fc_start_session`, la cola se llenaba de "huérfanos" que `_render_flashcard_session` descartaba, dejando la sesión vacía.
- Fix: filtrar `due_today` antes de calcular `n_due` y antes de llamar a `_fc_start_session`:
  ```python
  due_today = [c for c in due_today_raw if c.flashcard_front and c.is_classified]
  ```

### 3. Click en nodo filtra el mapa
Implementado en el Sprint 18 addendum. Verificado que permanece funcional. Tests confirman que la ruta correcta existe en el grafo.

### 4. Diagramas no se mostraban (RESUELTO)
**`ui/app.py` → `_empty_state` y `_TIMEOUT_RESULT`**

- Los campos `diagram_svg` y `suggested_concepts` no estaban en el estado inicial del grafo.
- Aunque LangGraph los propaga al hacer merge del resultado del `tutor_agent`, no incluirlos en el estado inicial causaba inconsistencia.
- Añadidos `"diagram_svg": ""` y `"suggested_concepts": []` a `_empty_state()` y `_TIMEOUT_RESULT`.

### 5. Timeout aumentado + progreso visual
**`ui/app.py`**

- `_GRAPH_TIMEOUT_SECONDS`: `30` → `60` segundos.
- El bloque de submit reemplaza `st.spinner()` por `st.status()` con mensajes de progreso:
  - `🔍 Analizando...`
  - `🧠 Procesando con IA...`
  - `🔗 Buscando conexiones...`
  - `✓ Listo` (al completar) / `Error al procesar` (si falla).

### 6. Personalización dinámica de ejemplos
**`agents/classifier_agent.py`**

- Basado en `user_profile.profession`, se añade automáticamente al `user_context` del clasificador:
  - `analista` / `banca` → "usa un ejemplo en crédito o banca"
  - `desarrollador` / `ingeniero` → "usa un ejemplo en código o arquitectura"
  - `diseñ` / `ux` → "usa un ejemplo en diseño de experiencia"
  - `emprend` / `negoci` → "usa un ejemplo en producto o negocio"
  - `estudiant` → "usa un ejemplo académico o conceptual"
  - Otro / default → "usa un ejemplo práctico relevante"

**`ui/components.py` → `render_concept_card`**

- El label `"Ejemplo en banca"` ahora es dinámico basado en `concept.category`:
  - Finanzas/banca → "Ejemplo en banca"
  - Inteligencia artificial/machine learning → "Ejemplo en IA"
  - Software/programación/tecnología → "Ejemplo en código"
  - Negocios/producto/marketing → "Ejemplo en negocio"
  - Diseño/experiencia de usuario → "Ejemplo en diseño"
  - Otras → "Ejemplo práctico"

### 7. Confirmación antes de reclasificar términos ya clasificados
**`agents/capture_agent.py`**

- Cuando un término ya existe con `is_classified=True`, en lugar de reclasificar silenciosamente, retorna `mode='confirm_reclassify'`.
- Términos con `is_classified=False` siguen retornando `mode='reclassify'` directamente.

**`agents/graph.py`**

- `_route_after_capture`: `confirm_reclassify` → `END` (igual que `clarify` y `spelling`).

**`agents/state.py`**

- Documentado el nuevo modo `confirm_reclassify` en el docstring de `NuraState`.

**`ui/app.py` → historial de la vista Descubrir**

- Badge `"¿Reclasificar?"` en teal (`#74c7ec`) para entradas `confirm_reclassify`.
- Banner azul claro con:
  - Texto: "Ya tengo '{term}' en tu mapa. ¿Es el mismo concepto o uno diferente?"
  - Botón **"Sí, actualizar contexto"** → llama `_handle_submit(term, user_context="[CLARIFIED]: reclasificar con contexto actualizado")` y continúa el pipeline de reclasificación.
  - Botón **"No, es diferente — buscar en web"** → llama `_handle_submit(term, user_context="[WEBSEARCH]: buscar definición...")` y activa `websearch_classify`.

**`tests/test_bugfixes.py`**

- `TestBug3ReclassifyClassified::test_classified_term_returns_reclassify` actualizado para esperar `mode='confirm_reclassify'` (comportamiento Sprint 20).

---

## Archivos modificados
| Archivo | Cambio |
|---|---|
| `ui/app.py` | Timeout 60s, st.status(), _empty_state con diagram_svg/suggested_concepts, flashcard loop (deferred), repasar ahora filter, confirm_reclassify banner |
| `ui/components.py` | Etiqueta dinámica de ejemplo según categoría |
| `agents/capture_agent.py` | confirm_reclassify para términos clasificados |
| `agents/classifier_agent.py` | Hint dinámico de ejemplo según profesión |
| `agents/state.py` | Documentación del modo confirm_reclassify |
| `agents/graph.py` | Ruta confirm_reclassify → END |
| `tests/test_sprint20.py` | 26 tests nuevos |
| `tests/test_bugfixes.py` | Actualización de test de reclasificación |
