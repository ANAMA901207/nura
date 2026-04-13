# Sprint 15 — Close: Onboarding y Perfil de Usuario

## Estado: CERRADO ✓

**Fecha:** 12 de abril de 2026
**Tests:** 146/146 passed, 0 regressions

---

## Objetivo cumplido

Flujo de onboarding completo de 4 pasos que personaliza la experiencia desde
el primer uso, con soporte para múltiples áreas de aprendizaje y niveles
diferenciados por área.  Los agentes de clasificación y tutoría leen el
nuevo formato de perfil y adaptan sus respuestas al contexto del usuario.

---

## Cambios implementados

### 1. Modelo de usuario ampliado

**`db/models.py`**
- Tres nuevos campos en `User` (todos `str`, default `""`):
  - `profession` — perfil profesional elegido en el onboarding.
  - `learning_area` — áreas de interés en formato comma-separated
    (p. ej. `"IA y tecnología, Finanzas y negocios"`).
  - `tech_level` — niveles por área en formato JSON serializado
    (p. ej. `'{"IA y tecnología": "Básico", "Finanzas y negocios": "Avanzado"}'`).

---

### 2. Migración idempotente

**`db/schema.py`**
- `_SPRINT15_USER_MIGRATIONS`: tres columnas `TEXT NOT NULL DEFAULT ''`
  para la tabla `users`.
- Bloque en `_run_migrations()` que aplica los `ALTER TABLE` con
  `OperationalError` silenciado para idempotencia.

---

### 3. Operaciones de perfil

**`db/operations.py`**
- `_row_to_user` lee los tres campos nuevos con fallback a `""`.
- `update_user_profile(user_id, profession, learning_area, tech_level) -> User`:
  persiste el perfil y devuelve el User refrescado.
- `needs_onboarding(user) -> bool`: `True` si cualquier campo está vacío.

---

### 4. Onboarding rediseñado — 4 pasos

**`ui/auth.py`**

Constantes actualizadas:
- `_PROFESSIONS` — sin cambios.
- `_LEARNING_AREAS` — reemplaza "Ambas" por "Desarrollo de software" y
  "Marketing y ventas". Ya no incluye "Otro" como opción directa del
  multiselect (se usa un `st.checkbox` separado).
- `_TECH_LEVELS` — sin cambios.

SVG Lucide inline añadidos: `_SVG_COMPASS`, `_SVG_LAYERS`, `_SVG_NETWORK`
para los tres puntos de valor de la pantalla de bienvenida.

Helper `_ob_header()`: logo Nura centrado reutilizable en todos los pasos.

`render_onboarding(user) -> bool` — flujo controlado por
`st.session_state.onboarding_step` (0-3):

**Paso 0 — Bienvenida** (`onboarding_step = 0`):
- Logo Nura + título "Bienvenido/a a Nura" + subtítulo "Tu tutor personal
  con memoria."
- Tres tarjetas con íconos SVG Lucide:
  - **Descubrir** (brújula): escribe cualquier término o pregunta.
  - **Dominar** (capas): flashcards inteligentes adaptativas.
  - **Conectar** (red): visualiza tu conocimiento como una constelación.
- Tagline en cursiva: *"Cuanto más uses Nura, más te conoce. Y cuanto más
  te conoce, mejor te enseña."*
- Botón "Empezar →" avanza al Paso 1.
- Barra de progreso en 0%.

**Paso 1 — Profesión** (`onboarding_step = 1`):
- `st.radio` con las opciones de `_PROFESSIONS`.
- Si elige "Otro" → aparece `st.text_input` libre inmediatamente.
- Guarda en `ob_profession`. Barra "Paso 1 de 3".

**Paso 2 — Áreas de aprendizaje** (`onboarding_step = 2`):
- `st.multiselect` con las 4 áreas (sin "Otro").
- `st.checkbox` "Otra área no listada" → despliega `st.text_input` libre.
- Al avanzar, consolida todas las áreas en `ob_areas` (lista).
- Si no se selecciona ninguna, usa la primera opción como fallback.
- Barra "Paso 2 de 3".

**Paso 3 — Nivel por área** (`onboarding_step = 3`):
- Un `st.radio` horizontal por cada área guardada en `ob_areas`, con key
  indexada `ob_level_0`, `ob_level_1`…
- Al hacer clic en "Empezar con Nura →":
  - Lee niveles de `st.session_state[ob_level_N]` por índice.
  - Construye `{"área": "nivel", …}` y lo serializa como JSON.
  - Llama a `update_user_profile`.
  - Actualiza `st.session_state["user"]` y limpia el estado temporal.
- Barra "Paso 3 de 3".

---

### 5. Formato de datos del perfil

| Campo | Formato en BD | Ejemplo |
|-------|---------------|---------|
| `profession` | cadena simple | `"Desarrollador/ingeniero"` |
| `learning_area` | comma-separated | `"IA y tecnología, Finanzas y negocios"` |
| `tech_level` | JSON serializado | `'{"IA y tecnología": "Básico", "Finanzas y negocios": "Avanzado"}'` |

Compatibilidad hacia atrás: `tech_level` legado (cadena simple como
`"Intermedio"`) es parseado como `{"general": "Intermedio"}` por los
helpers `_parse_tech_level`.

---

### 6. Agente de clasificación adaptativo

**`agents/classifier_agent.py`**
- Nueva función `_parse_tech_level(str) -> dict[str, str]`:
  acepta JSON nuevo (dict) o cadena legada (devuelve `{"general": nivel}`).
- El bloque de perfil en el nodo `classifier_agent` construye un hint
  específico por área cuando hay múltiples niveles:
  `"niveles: Avanzado en Finanzas y negocios, Básico en IA y tecnología"`.
- El hint se añade a `user_context` antes de llamar a `classify_concept`.

---

### 7. Tutor adaptativo mejorado

**`agents/tutor_agent.py`**
- Misma función `_parse_tech_level` que el clasificador.
- `_build_tutor_system_prompt(user_profile)` reconstruido:
  - Genera `level_desc` compacto por área.
  - Parsea `learning_area` como lista para describir múltiples áreas.
  - Fallback extendido en `_PROFESSION_EXAMPLES`:
    cubre "Marketing y ventas" → ejemplos de emprendedor;
    "Desarrollo de software" → ejemplos de ingeniería.
  - Ejemplo de prompt generado para un usuario real:
    *"El usuario es Arquitecta (Avanzado en Finanzas y negocios, Básico en
    IA y tecnología). Sus áreas de interés son: Finanzas y negocios,
    IA y tecnología. Los ejemplos deben referirse a crédito bancario,
    NIIF, riesgo crediticio…"*

---

### 8. Estado del grafo

**`agents/state.py`**
- Campo `user_profile: dict` (sin cambios desde el sprint base).
  Contiene `profession`, `learning_area`, `tech_level` en sus formatos nuevos.

---

### 9. Integración en la app principal

**`ui/app.py`**
- Onboarding gate: `needs_onboarding(user)` → `render_onboarding(user)` →
  `st.stop()`.
- Carga de perfil en `st.session_state.user_profile` tras el onboarding.
- `_empty_state` y `_invoke_with_timeout` pasan `user_profile` al grafo.
- **Sidebar "Mi perfil"** actualizado para el nuevo formato:
  - `st.multiselect` para áreas (default = áreas actuales parseadas).
  - `st.selectbox` de nivel único (aplicado a todas las áreas al guardar).
  - Al guardar: construye `tech_level` como JSON `{área: nivel}`.

---

## Archivos modificados

| Archivo | Tipo de cambio |
|---------|----------------|
| `db/models.py` | 3 campos nuevos en `User` |
| `db/schema.py` | `_SPRINT15_USER_MIGRATIONS` + bloque en `_run_migrations` |
| `db/operations.py` | `_row_to_user` actualizado; `update_user_profile`; `needs_onboarding` |
| `agents/state.py` | Campo `user_profile: dict` |
| `agents/classifier_agent.py` | `_parse_tech_level`; hint multi-área en `classifier_agent` |
| `agents/tutor_agent.py` | `_parse_tech_level`; `_build_tutor_system_prompt` mejorado |
| `ui/auth.py` | Onboarding 4 pasos completo; `_LEARNING_AREAS` actualizado |
| `ui/app.py` | Onboarding gate; carga de perfil; sidebar "Mi perfil" nuevo formato |
| `tests/test_sprint15.py` | Harness (5 tests) |
| `tests/test_agents.py` | `user_profile: {}` en `_EMPTY_STATE` |

---

## Harness verificado

- `test_update_user_profile_persists` — persiste los 3 campos en la BD ✓
- `test_needs_onboarding_with_empty_fields` — True con cualquier campo vacío ✓
- `test_needs_onboarding_with_full_profile` — False con perfil completo ✓
- `test_classifier_receives_user_profile` — user_context incluye el perfil ✓
- `test_tutor_receives_user_profile` — prompt adaptado por profesión y área ✓
- **146/146 passed, 0 regressions ✓**
