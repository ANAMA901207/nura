# Sprint Redesign Close — Replicación del diseño v0.dev en Streamlit

## Objetivo

Replicar fielmente el diseño visual generado en v0.dev (`v0_reference/`) en la
interfaz Streamlit existente (`ui/app.py` y `ui/components.py`), sin tocar lógica
de agentes, base de datos, ni tests.

---

## Referencia de diseño

Archivos fuente leídos para extraer tokens y componentes:

| Archivo | Qué aportó |
|---|---|
| `v0_reference/styles/globals.css` | Paleta de colores del tema dark (background, surface, primary, muted, border) |
| `v0_reference/components/nura/nura-logo.tsx` | SVG de constelación + tipografía del logo |
| `v0_reference/components/nura/sidebar.tsx` | Layout del sidebar: logo, avatar, nav, streak, logout |
| `v0_reference/components/nura/chat-tab.tsx` | Insight banner, input con ícono, concept card, category badges |
| `v0_reference/components/nura/aprendizaje-tab.tsx` | Metric cards, flashcard, progress bars |
| `v0_reference/components/nura/mapa-tab.tsx` | Estilo del mapa: `bg-card border`, node/edge colors |
| `v0_reference/app/page.tsx` | Layout general: sidebar fijo + main content scrollable |

---

## Tokens de diseño (v0 → Streamlit)

| Token | Valor | Uso |
|---|---|---|
| `primary` | `#60a0ff` | N bold, active tabs, banners, badges, links |
| `background` | `#1e1e2e` | Fondo base, sidebar |
| `surface` | `#313244` | Cards, inputs, items de nav, expanders |
| `border` | `#45475a` | Bordes sutiles de todos los contenedores |
| `text` | `#cdd6f4` | Texto principal legible |
| `muted` | `#6c7086` | Labels secundarios, placeholder, texto de apoyo |
| `success` | `#a6e3a1` | Respuestas correctas, mastery alto |
| `warning` | `#f9e2af` | Quiz, dot amarillo de constelación |
| `error` | `#f38ba8` | Respuestas incorrectas, dot rosa de constelación |
| `purple` | `#cba6f7` | Reclassify, review, dot morado de constelación |
| `teal` | `#74c7ec` | Conexiones, dot celeste de constelación |
| `orange` | `#fab387` | Acento del ícono de streak (no reemplaza primary) |

**Cambio principal:** primary pasó de `#89b4fa` (Catppuccin blue) → `#60a0ff` (Nura blue del v0).

---

## Archivos modificados

### `ui/app.py`

#### 1. Nuevas constantes de diseño

**`_NURA_LOGO_HTML`** (nuevo): replica el componente `NuraLogo` del v0.

```html
<!-- N bold en #60a0ff + SVG de constelación -->
<span style="font-size:2.4rem; font-weight:900; color:#60a0ff;">N</span>
<svg width="36" height="30" viewBox="0 0 32 28">
  <!-- 5 líneas de conexión en #6c7086 stroke-width 0.7 -->
  <!-- 5 nodos: amarillo #f9e2af, morado #cba6f7, verde #a6e3a1,
                teal #74c7ec, rosa #f38ba8 -->
</svg>
<!-- Texto "Nura" en #cdd6f4 + "aprende · conecta · domina" en #6c7086 -->
```

#### 2. CSS global (`_CSS`) — cambios completos

| Sección | Antes | Ahora |
|---|---|---|
| Tab active | `border-bottom: 2px solid #89b4fa` | `#60a0ff` |
| Input focus | `border-color: #89b4fa` | `#60a0ff` |
| Button border | `border: 1px solid #89b4fa33` | `#60a0ff33` |
| Button hover | `box-shadow: 0 0 8px #89b4fa33` | `#60a0ff33` |
| Spinner | `color: #89b4fa` | `#60a0ff` |
| Sidebar bg | *(no existía)* | `background: #1e1e2e !important` |
| Sidebar button | *(no existía)* | Estilo transparente diferenciado del botón primario |
| Card radius | `10px` (varios) | `12px` consistente |
| Selectbox/multiselect | Sin estilo | `#313244` bg + `#45475a` border |
| Slider | Sin estilo | `background: #60a0ff` para el thumb |

Nueva clave CSS añadida: `initial_sidebar_state="expanded"` en `st.set_page_config`.

#### 3. Sidebar rediseñado (`main()`)

**Antes:**
```
👤 username
[🚪 Cerrar sesión]
```

**Ahora (replica sidebar.tsx del v0):**
```
[NuraLogo SVG]  ← N + constelación + "Nura" + subtítulo

[Avatar #60a0ff con iniciales] username
                               Nurian   ← badge en #60a0ff

Navegación
💬 Chat
📚 Aprendizaje
🗺️ Mapa

──────────────────
🔥 N días seguidos   ← streak con dato real de la BD

[🚪 Cerrar sesión]   ← estilo sutil, borde #45475a
```

- El avatar calcula las iniciales desde el `username` (hasta 2 palabras).
- El streak usa `get_streak(user_id)` — dato en vivo.
- Los ítems de navegación son decorativos (la navegación funcional sigue en `st.tabs`).
- Se eliminó el bloque "N + gradient Nura" del área principal.

#### 4. Color updates en el resto de `app.py`

| Ubicación | Antes | Ahora |
|---|---|---|
| Badge modo `question` | `#89b4fa` | `#60a0ff` |
| Badge web search | `#89b4fa` | `#60a0ff` |
| "Explorar concepto" label | `#89b4fa` | `#60a0ff` |
| "Insight semanal" label | `#89b4fa` | `#60a0ff` |
| Bar chart del perfil | `color="#89b4fa"` | `color="#60a0ff"` |
| Tutor response card | `border-radius:10px` | `border-radius:12px` |

---

### `ui/components.py`

#### 1. `render_insight_banner` — rediseño completo

**Antes:** gradiente `linear-gradient(135deg, #1e2a3d, #1e1e2e)` con borde blue complejo.

**Ahora:** replica exactamente `bg-card border-l-4 border-l-primary` del v0:
```css
background: #313244;           /* bg-card */
border: 1px solid #45475a;
border-left: 4px solid #60a0ff; /* border-l-primary */
border-radius: 12px;
```
El label "Nura dice" usa `color: #60a0ff`, `font-size: 0.68rem`, `letter-spacing: 0.12em`.

#### 2. `render_concept_card` — card background aplanada

**Antes:** `background: linear-gradient(135deg, #313244 0%, #1e1e2e 100%)` — gradiente sutil.

**Ahora:** `background: #313244` — superficie plana como en v0 (`bg-card`). El borde izquierdo de color de categoría se mantiene para la identidad visual.

#### 3. Paleta de categorías — "crédito" actualizada

```python
"credito": "#60a0ff"  # era "#89b4fa", ahora usa el primary del v0
```

#### 4. Otros colores actualizados

| Función | Elemento | Antes | Ahora |
|---|---|---|---|
| `render_flashcard` | label FRENTE | `#89b4fa` | `#60a0ff` |
| `render_knowledge_map` | edge highlight | `"highlight": "#89b4fa"` | `"#60a0ff"` |
| `render_concept_detail_panel` | "N conexiones" label | `#89b4fa` | `#60a0ff` |
| `render_sources` | border-left + link color | `#89b4fa` | `#60a0ff` |

---

## Lo que NO cambió

- Toda la lógica de agentes (`agents/`)
- Base de datos (`db/`)
- Todos los tests (`tests/`)
- Funcionalidad de flashcards, quiz, mapa interactivo, repaso SM-2
- Auth flow (`ui/auth.py`)
- Sprint 12 insight banner (solo se cambió el estilo, no la lógica)

---

## Resultados de tests

```
121/121 passed — 0 regressions (36 s)
Ignorados (requieren API real): test_agents.py, test_sprint4.py, test_sprint10.py
```

---

## Notas de implementación

**NuraLogo como HTML inline:** Streamlit no soporta componentes React, por lo que
el logo se renderiza como `st.markdown(..., unsafe_allow_html=True)` con el SVG
embebido directamente en el HTML del sidebar. Las posiciones de los nodos y los
colores son iguales al `nura-logo.tsx` original.

**Sidebar navigation decorativa:** El v0 usa el sidebar como único sistema de
navegación. En Streamlit, `st.tabs` proporciona la navegación funcional. Se añadieron
los ítems de nav (💬 Chat, 📚 Aprendizaje, 🗺️ Mapa) como elementos visuales no
interactivos para replicar la apariencia del v0 sin duplicar la lógica de routing.

**Avatar con iniciales:** Se computan en tiempo de ejecución desde
`st.session_state["user"].username` — si el username tiene dos palabras toma la
inicial de cada una; si es una sola palabra, los primeros dos caracteres.

**`initial_sidebar_state="expanded"`:** Cambiado de `"collapsed"` para que el
sidebar sea visible por defecto y el usuario vea el logo y su perfil al entrar.
