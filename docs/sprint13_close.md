# Sprint 13 — Close: Bugs visuales y nombres

## Estado: CERRADO ✓

**Fecha:** 12 de abril de 2026
**Tests:** 121/121 passed, 0 regressions

---

## Objetivo cumplido

Limpieza visual completa de la interfaz de Nura y establecimiento
de la nomenclatura definitiva del producto.

---

## Cambios implementados

### 1. Íconos SVG consistentes

Eliminados todos los emojis visibles en la UI (excepto 🔥 del streak).
Reemplazados por íconos SVG Lucide inline en los tres archivos UI:

**`ui/app.py`**
- `🔁 Sesión de repaso` → botón de texto `"Repasar"`
- `🧩 Quiz` → botón de texto `"Quiz"`
- `🔄 Reclasificado` en badge → `"↻ Reclasificado"`
- `💬 Tutor`, `🔁 Repaso`, `🧩 Quiz` en badges → texto limpio
- `🌐` en badge de búsqueda web → eliminado
- `🧠` en estado vacío del historial → SVG Lucide sparkles (48px)
- `👁 Voltear`, `✅ Lo sabía`, `❌ No lo sabía` → texto limpio
- `🃏`, `💬` en estilo de aprendizaje preferido → texto
- `📍 Área a reforzar` → eliminado el ícono
- `⚠️` en alerta de sin clasificar → eliminado
- `📅` en título "Para repasar hoy" → eliminado
- `▶️ Repasar ahora` → `"Repasar ahora (N)"`
- `🎉` en pantalla de sesión completada → SVG Lucide check-circle (40px)
- `🔄 Nueva sesión` → texto limpio
- `▶️ Iniciar sesión de flashcards` → `"Iniciar flashcards"`

**`ui/components.py`**
- `⚠️ Sin clasificar` badge → `"Sin clasificar"` sin ícono
- `💡` en analogía del concepto → eliminado
- `✏️ Corregir clasificación` expander → texto limpio
- `💾 Guardar corrección` → texto limpio
- `💡` / `❓` / `📖` en flashcard → SVG Lucide inline (32px):
  - Frente: `help-circle` en `#60a0ff`
  - Reverso: `lightbulb` en `#f9e2af`
  - Sin flashcard: `book-open` en `#a6adc8`
- `🔥 Racha: N` en streak de flashcard → **conservado** (excepción)
- `🔗` en panel de conexiones → eliminado
- `✅` / `❌` en quiz → `✓` / `✗` (Unicode, no emoji)
- `💡` en explicación de quiz → eliminado
- `🧠` en insight banner → SVG Lucide sparkles (18px, `#60a0ff`)

**`ui/auth.py`**
- `🔑 Iniciar sesión` tab → `"Iniciar sesión"`
- `✨ Registrarse` tab → `"Registrarse"`
- `🎉` en mensajes de éxito (login y registro) → eliminado

---

### 2. Texto SM-2 humanizado

Eliminado todo el lenguaje técnico de SM-2 visible al usuario:

| Antes | Después |
|-------|---------|
| `SM-2 ha programado X concepto(s) para hoy:` | `Tienes X concepto(s) listos para repasar hoy.` |
| `¡Al día con SM-2! No hay conceptos programados para hoy.` | `¡Estás al día! No tienes conceptos pendientes de repaso.` |
| `Intervalo SM-2: Nd` | `Próximo en Nd` |
| `### 📅 Para repasar hoy` | `### Para repasar hoy` |

---

### 3. Botones de acción prominentes en Dominar

Reestructurada la vista `_render_view_dominar()` para que los botones
de acción aparezcan **inmediatamente después del Resumen de hoy**, antes
de la lista de conceptos.

Nueva estructura de la vista Dominar:

```
[Perfil de dominio]
─────────────────────────────────────────────
[Resumen de hoy]

[ Repasar ahora (N) ]  [ Iniciar flashcards (N) ]
─────────────────────────────────────────────
[Mis conceptos]
─────────────────────────────────────────────
[Para repasar hoy — solo la lista, sin botón redundante]
─────────────────────────────────────────────
[Flashcards]
```

Ambos botones prominentes muestran el conteo entre paréntesis y se
deshabilitan automáticamente cuando no hay elementos disponibles.

---

### 4. Nomenclatura definitiva de navegación

Renombradas las tres vistas en todo el código:

| Antes | Después |
|-------|---------|
| Chat | **Descubrir** |
| Aprendizaje | **Dominar** |
| Mapa | **Conectar** |

Actualizaciones aplicadas en:
- `st.session_state.current_view` (valores: `"descubrir"`, `"dominar"`, `"conectar"`)
- `_NAV_CONFIG` en el sidebar (labels y keys de botones)
- Dispatch en `main()` (ramas `if/elif`)
- Nombres de funciones: `_render_view_descubrir()`, `_render_view_dominar()`, `_render_view_conectar()`
- Títulos de sección: `"### Descubrir"`, `"### Conectar"`, `"### Perfil de dominio"`
- Mensaje de estado vacío: `"Ve a Descubrir para agregar el primero."`

---

## Archivos modificados

| Archivo | Tipo de cambio |
|---------|---------------|
| `ui/app.py` | Renombrado 3 funciones, eliminados 15+ emojis, reestructurado Dominar, SM-2 humanizado, dispatch actualizado |
| `ui/components.py` | Eliminados 10+ emojis, SVG inline en flashcard e insight banner |
| `ui/auth.py` | Eliminados 4 emojis de tabs y mensajes de éxito |

---

## Harness verificado

- Sin emojis en la UI (excepto 🔥 streak) ✓
- Texto SM-2 eliminado de todas las vistas ✓
- Botones de repaso visibles sin scroll en Dominar ✓
- Nombres Descubrir / Dominar / Conectar en toda la app ✓
- 121/121 tests passed, 0 regressions ✓
