# Sprint 36 — Cierre: Mapa jerárquico visual

## Alcance entregado

- **`ui/components.py`**
  - **`render_hierarchy_svg(tree, highlighted_id=None, *, user_id=None) -> str`:** SVG puro (sin librerías extra), layout top-down, ancho fijo 680 px, alto según layout. Colores por nivel: raíz `#185FA5`, nivel 1 `#0F6E56`, nivel 2+ `#5F5E5A`, resaltado `#534AB7` (con `highlighted_id` + `user_id` para resolver el término). Nodos en `rect` con `rx="8"`, texto centrado, flechas padre→hijo con `marker-end`. Texto «← estás aquí» junto al nodo resaltado. Árbol vacío: mensaje «Sin jerarquía registrada» sin lanzar error.
  - **`render_concept_hierarchy_mini(user_id, concept_id)`:** Usa `get_concept_tree` y `get_hierarchy`; si el concepto no participa en jerarquía → `st.caption` con categoría; si participa → mini SVG vía `st.components.v1.html` (altura 200).
- **`ui/app.py`**
  - Vista **Dominar:** en cards con acciones, sección «📍 Dónde encaja» tras la flashcard, llamando a `render_concept_hierarchy_mini`.
  - Vista **Conectar:** radio de tres opciones (mapa de conexiones, árbol jerárquico texto, árbol visual); la tercera muestra el SVG completo con `components.html(..., height=600, scrolling=True)`.
- **`tests/test_sprint36.py`:** cinco tests de harness; `_make_concept` alineado al `INSERT` de conceptos usado en otros sprints (12 columnas + `INSERT OR IGNORE`).

## Verificación

Última corrida local:

`python -m pytest tests/ --tb=no -q` → **393 passed, 4 skipped** (7 subtests passed; advertencias previas en `test_sprint9` por `return` en tests legacy).

## Archivos tocados en este sprint

- `ui/components.py`
- `ui/app.py`
- `tests/test_sprint36.py`
- `docs/sprint36_close.md`
