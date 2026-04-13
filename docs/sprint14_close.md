# Sprint 14 — Close: UX e Interacción

## Estado: CERRADO ✓

**Fecha:** 12 de abril de 2026
**Tests:** 141/141 passed, 0 regressions

---

## Objetivo cumplido

Cuatro mejoras de interacción que hacen la captura de conocimiento más
inteligente y el manejo de conceptos más flexible.

---

## Cambios implementados

### 1. Detección de ambigüedad (`mode='clarify'`)

Antes de capturar un término, el agente llama a Gemini para detectar si
tiene múltiples significados muy diferentes entre sí.

**`agents/capture_agent.py`**
- Nueva función `_is_ambiguous(term) -> dict` con prompt JSON:
  `{"ambiguous": bool, "meanings": ["sig. 1", "sig. 2"]}`.
- Activada para términos de ≤ 4 palabras como prioridad 4b (después de
  comprobar ortografía, antes de capturar).
- Si `ambiguous=True`, devuelve `mode='clarify'` con los significados en
  `clarification_options`. Fallo de API → pasa directamente a captura.

**`agents/graph.py`**
- `_route_after_capture` devuelve `END` para `mode='clarify'`.

**`ui/app.py`** — historial de Descubrir:
- Badge "Ambigüedad" en naranja (`#fab387`).
- Banner con el mensaje `"'término' puede significar varias cosas — ¿a cuál
  te refieres?"` y un botón por cada significado.
- Al hacer clic en un botón, reenvía el término original con el significado
  elegido como `user_context` para clasificar con el contexto correcto.

---

### 2. Corrección ortográfica (`mode='spelling'`)

Antes de capturar, el agente detecta si el término parece tener un error
ortográfico en contexto técnico/financiero.

**`agents/capture_agent.py`**
- Nueva función `_check_spelling(term) -> dict` con prompt JSON:
  `{"has_typo": bool, "suggested": "término correcto o null"}`.
- Activada para términos de ≤ 5 palabras como prioridad 4a (antes de la
  detección de ambigüedad).
- Si `has_typo=True` y hay sugerencia, devuelve `mode='spelling'` con
  la corrección en `spelling_suggestion`. Fallo de API → pasa a captura.

**`agents/graph.py`**
- `_route_after_capture` devuelve `END` para `mode='spelling'`.

**`ui/app.py`** — historial de Descubrir:
- Badge "Ortografía" en rojo tenue (`#f38ba8`).
- Banner con `"¿Quisiste decir 'sugerencia'?"` y dos botones:
  - **Sí, usar 'X'** → reenvía la sugerencia directamente.
  - **No, capturar como está** → reenvía el término original con un
    `user_context` de bypass para saltarse el chequeo.

---

### 3. Editar y eliminar conceptos

Los conceptos en "Mis conceptos" ahora son editables y eliminables
directamente desde la UI.

**`db/operations.py`**
- `update_concept_fields` ahora admite `term` en el set de campos
  permitidos (antes solo permitía category, subcategory, explanation, etc.).
- Nueva función `delete_concept(concept_id, user_id) -> bool`:
  elimina primero todas las conexiones donde el concepto aparezca como
  extremo A o B (cascada manual) y luego borra el concepto. Devuelve
  `True` si existía, `False` si no se encontró.

**`ui/components.py`** — `render_concept_card`
- Nuevo parámetro `show_actions: bool = False`.
- Cuando `True`, muestra dos columnas bajo el contenido de la tarjeta:
  - **Editar** (expander con form): campos `term`, `category`,
    `explanation`; al guardar llama a `update_concept_fields`.
  - **Eliminar** (botón): al hacer clic activa `st.session_state
    [pending_delete_{id}]` y muestra un `st.warning` de confirmación
    con botones **Sí, eliminar** y **Cancelar**.

**`ui/app.py`** — vista Dominar, sección "Mis conceptos"
- Reemplazado el `st.dataframe` por iteración individual de conceptos
  con `render_concept_card(c, show_edit=False, show_actions=True)`.

---

### 4. Filtro de mapa en Conectar (`map_filter_concept_id`)

Al explorar un concepto en la vista Conectar, el mapa puede filtrarse para
mostrar solo ese nodo y sus vecinos directos.

**`ui/app.py`** — vista Conectar
- Nueva clave `st.session_state.map_filter_concept_id` (inicializada en
  `_init_session` como `None`).
- Cuando un concepto está seleccionado en el selectbox "Explorar concepto",
  aparece el botón **"Ver solo '[término]' en el mapa"** que asigna el ID
  a `map_filter_concept_id` y fuerza rerun.
- Si el filtro está activo, el mapa renderiza solo:
  - El nodo focal.
  - Sus vecinos directos (todos los nodos conectados por 1 arista).
  - Las aristas directas que los unen.
- Un banner naranja informa cuántas conexiones directas tiene el nodo.
- El botón **"Ver todo el mapa"** borra `map_filter_concept_id` y restaura
  la vista completa.

---

### 5. Infraestructura

**`agents/state.py`**

| Campo nuevo | Tipo | Descripción |
|-------------|------|-------------|
| `clarification_options` | `list[str]` | Significados posibles para `mode='clarify'` |
| `spelling_suggestion` | `str` | Corrección sugerida para `mode='spelling'` |

**`_empty_state()` en `ui/app.py`**
- Añadidos `clarification_options: []` y `spelling_suggestion: ""`
  al estado inicial del grafo.

**`tests/test_agents.py`**
- Actualizado `_EMPTY_STATE` con los nuevos campos.
- Añadidos patches de módulo `_no_typo` y `_no_ambig` que deshabilitan
  `_check_spelling` e `_is_ambiguous` para los tests de captura/clasificación
  existentes (esos tests verifican el pipeline, no la ortografía/ambigüedad).

---

## Archivos modificados

| Archivo | Tipo de cambio |
|---------|---------------|
| `agents/state.py` | Añadidos 2 campos nuevos |
| `agents/capture_agent.py` | Añadidas `_is_ambiguous`, `_check_spelling`, `_call_gemini_json`; integradas en prioridades 4a-4b |
| `agents/graph.py` | Rutas `clarify` y `spelling` → `END` |
| `db/operations.py` | `delete_concept` nuevo; `term` en `update_concept_fields` |
| `ui/components.py` | `render_concept_card` con `show_actions=True` |
| `ui/app.py` | Historial: `clarify`/`spelling`; Dominar: cards con acciones; Conectar: filtro de mapa |
| `tests/test_sprint14.py` | Harness nuevo (5 tests) |
| `tests/test_agents.py` | Patches de módulo + nuevos campos en `_EMPTY_STATE` |

---

## Harness verificado

- `test_ambiguous_term_activates_clarify` — mode='clarify' con Gemini mockeado ✓
- `test_delete_concept_removes_concept_and_connections` — cascada correcta ✓
- `test_update_concept_fields_persists` — term + category + explanation ✓
- `test_map_filter_logic` — subgrafo incluye vecinos, excluye desconectados ✓
- `test_spelling_check_activates_spelling` — mode='spelling' con sugerencia ✓
- 141/141 passed, 0 regressions ✓
