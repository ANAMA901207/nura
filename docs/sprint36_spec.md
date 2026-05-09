# Sprint 36 — Mapa jerárquico visual

## Objetivo
Mostrar visualmente dónde encaja cada concepto en el
universo de conocimiento del usuario — un árbol
estructural completo con el concepto resaltado.

## Diseño visual (Opción C)
- Árbol jerárquico de arriba hacia abajo
- Nodo raíz (categoría) en azul arriba
- Nodos intermedios (subcategorías) en teal
- Nodos hoja (conceptos) en gris
- El concepto actual resaltado en púrpura con borde
- Texto "← estás aquí" junto al concepto resaltado
- Generado como SVG dinámico con pyvis o SVG directo

## Dónde aparece

### 1. Dentro de la card del concepto (Mis conceptos)
- Al expandir un concepto en vista Dominar →
  sección "📍 Dónde encaja" muestra el mini-árbol
- El árbol muestra: Categoría → Subcategoría →
  Concepto (resaltado) + hermanos en la misma rama
- Tamaño compacto — cabe dentro del expander

### 2. Vista Conectar — nueva pestaña "Árbol visual"
- Toggle de 3 opciones:
  "🔗 Mapa de conexiones" (pyvis actual)
  "🌳 Árbol jerárquico" (texto, ya existe)
  "🗺️ Árbol visual" (nuevo — SVG dinámico)
- El árbol visual muestra TODOS los conceptos del
  usuario organizados jerárquicamente
- Click en un nodo → muestra definición del concepto

## Generación del SVG
- Función `render_hierarchy_svg(concepts, hierarchy,
  highlighted_concept_id) -> str`
- Usa los datos de `get_concept_tree(user_id)` que
  ya existe en operations.py
- Layout top-down: raíz arriba, hojas abajo
- Colores según nivel: azul (raíz), teal (nivel 2),
  gris (nivel 3+), púrpura (concepto resaltado)
- Flechas con marker-end
- Tamaño dinámico según cantidad de nodos

## Archivos a modificar
- `ui/components.py` — `render_hierarchy_svg()`
  y `render_concept_hierarchy_mini()` para cards
- `ui/app.py` — toggle en Conectar + sección en
  cards de Dominar

## Harness
- `test_render_hierarchy_svg_returns_string`
- `test_hierarchy_svg_contains_highlighted_node`
- `test_hierarchy_svg_has_root_node`
- `test_mini_hierarchy_renders_without_crash`
- `test_hierarchy_toggle_option_exists`

## Reglas
- SVG puro — no librerías externas adicionales
- Si no hay jerarquía para un concepto → mostrar
  solo categoría como nodo raíz
- No romper tests existentes
- Correr pytest al cerrar y crear sprint36_close.md