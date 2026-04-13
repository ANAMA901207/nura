# Sprint 21 — Close: UX y diseño

## Resultado del harness

**281 passed, 0 regressions** (1 fallo pre-existente en `test_sprint4` que requiere clave Gemini real, sin relación con este sprint).

---

## Items implementados

### 1. Campo contexto eliminado (`ui/app.py`)
- Removido el `st.text_input` de "Contexto opcional" del formulario en `_render_view_descubrir`.
- El formulario queda con un solo campo limpio + botón Enviar.
- `_handle_submit` se llama sin `user_context` explícito desde el formulario principal.

### 2. Módulo Dominar rediseñado (`ui/app.py`)
Nuevo orden de secciones con separadores visuales claros:
- **Cards de acción rápida**: "Repasar hoy" (con acento azul, SVG refresh) y "Quiz rápido" (acento morado, SVG brain) como cards estilizadas con descripción, seguidas de botones Streamlit funcionales.
- **Resumen del día**: título tipo label en uppercase, 3 métricas.
- **Flashcards**: solo se muestra si hay sesión activa o conceptos pendientes (oculto cuando no hay nada).
- **Mis conceptos**: cada categoría en un `st.expander(expanded=False)` — colapsado por defecto, sin scroll infinito.
- **Perfil de dominio**: sin cambios.

### 3. Toast motivacional (`ui/components.py`)
- Nueva función `render_motivational_toast(message)` → usa `st.toast(message, icon='⭐')` nativo de Streamlit.
- Aparece en esquina inferior derecha, desaparece automáticamente, no bloquea la UI.
- `render_motivational_banner` mantenida como alias de backward compatibility (tests existentes siguen pasando).
- Actualizado en `ui/app.py`: todas las llamadas usan `render_motivational_toast`.

### 4. Nombres consistentes
- Badge "Sin clasificar" → **"Pendiente"** en `render_concept_card`.
- Expander "Corregir clasificación" → **"Editar concepto"** (en historial y en Mis conceptos).
- Fallback `current_view` en sidebar: `"chat"` → `"descubrir"`.
- Texto "sin clasificar" en alerta de dominar → "pendiente".

### 5. Botón editar inline (`ui/components.py`)
- Cuando `show_actions=True`, se usan `st.columns([11, 1])` para mostrar el header de la tarjeta junto a un botón ✏️ inline.
- Al hacer click, `st.session_state[f"_card_edit_{id}_{index}"]` se activa y aparece un expander "Editar concepto" con el formulario de edición (Guardar / Cancelar).
- El formulario de `show_edit` (historial) también dice "Editar concepto".

### 6. Click en nodo filtra mapa
- **`ui/components.py`**: actualizado JS en `render_knowledge_map` de `'selectNode'` a `'click'` (vis.js), con formato de mensaje `{nuranodeclick: nodeId}`.
- **`ui/app.py`**: listener en `_render_view_conectar` actualizado para aceptar ambos formatos (`evt.data.nuranodeclick` y el legado `evt.data.type === 'nura_node_click'`).

---

## Archivos modificados

| Archivo | Cambios |
|---|---|
| `ui/app.py` | Contexto eliminado, Dominar rediseñado, toast en ambos lugares, `current_view` default, texto "pendiente", listener postMessage actualizado |
| `ui/components.py` | Badge "Pendiente", expander "Editar concepto", botón inline show_actions, `render_motivational_toast`, `render_motivational_banner` como alias, JS `'click'` + `nuranodeclick` |
| `tests/test_sprint21.py` | Nuevo harness (22 tests) |
| `tests/test_sprint5.py` | Actualizado `test_unclassified_concept_shows_badge`: "Sin clasificar" → "Pendiente" |
| `tests/test_sprint16.py` | Actualizado `test_message_content_is_escaped`: verifica `st.toast` en lugar de `st.markdown` |
