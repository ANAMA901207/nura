# Sprint 31 — Brechas y Progreso por área

## Objetivo
Mostrarle al usuario qué le falta aprender y cómo
ha crecido su conocimiento con el tiempo.

## Funcionalidad 1 — Vista de brechas
Nura detecta conceptos "huérfanos" — nodos sin
conexiones en el mapa — y los presenta como
oportunidades de aprendizaje.

### Comportamiento
- En vista Conectar → sección "Brechas detectadas"
- Lista de conceptos sin conexiones con sugerencia:
  "LangGraph está solo en tu mapa. ¿Quieres entender
  cómo se relaciona con Python o con Agentes?"
- Click en sugerencia → abre tutor con esa pregunta
- En Telegram → `/brechas` lista los conceptos solos

## Funcionalidad 2 — Progreso por área en el tiempo
Gráfica que muestra cómo ha crecido el conocimiento
del usuario semana a semana por categoría.

### Comportamiento
- En vista Dominar → nueva sección "Mi progreso"
- Gráfica de líneas: eje X = semanas, eje Y = conceptos
  acumulados, una línea por categoría
- Usando st.line_chart o plotly
- Filtro por categoría y por rango de tiempo

## Archivos a modificar
- `db/operations.py` — funciones:
  `get_orphan_concepts(user_id) -> list[dict]`
  `get_concepts_by_week(user_id) -> list[dict]`
- `ui/app.py` — sección brechas en Conectar
  y gráfica de progreso en Dominar
- `ui/components.py` — `render_progress_chart`
- `bot/handlers.py` — comando `/brechas`

## Harness
- `test_get_orphan_concepts_returns_isolated`
- `test_get_orphan_concepts_excludes_connected`
- `test_get_concepts_by_week_structure`
- `test_brechas_command_telegram`
- `test_progress_chart_has_data`

## Reglas
- Si no hay brechas → mensaje positivo
  "¡Tu mapa está bien conectado!"
- Si no hay suficiente data para la gráfica
  (menos de 2 semanas) → mensaje motivacional
- No romper tests existentes
- Correr pytest al cerrar y crear sprint31_close.md