# Sprint 31 Close — Brechas y progreso por área

## Resultado del harness

```
tests/test_sprint31.py: 6 passed, 0 failed
Suite completa tests/: 345 passed, 3 failed (348 tests totales)
```

Los 3 fallos de la suite completa son llamadas reales a Gemini (`tests/test_agents.py` ×2, `tests/test_sprint4.py::test_tutor_uses_bd_context`) cuando la API no responde como esperan los tests; no son regresiones del Sprint 31.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `db/operations.py` | `get_orphan_concepts(user_id)`: conceptos sin filas en `connections` (ni `concept_id_a` ni `concept_id_b`). `get_concepts_by_week(user_id)`: acumulado por semana ISO (`YYYY-Www`) y categoría, orden ascendente por semana. |
| `ui/components.py` | `render_progress_chart(data)`: mensaje si vacío o menos de 2 semanas distintas; si no, `pandas` + `st.line_chart` en formato ancho (categorías en columnas). |
| `ui/app.py` | Conectar: sección «Brechas detectadas», botón «Explorar conexión» → Descubrir con texto en `discover_chat_input`. Descubrir: `key="discover_chat_input"` en el input. Dominar: «Mi progreso», `get_concepts_by_week`, selectbox de categoría y `render_progress_chart`. |
| `bot/handlers.py` | Comando `/brechas`, `handle_brechas`, mención en `/start`. |
| `requirements.txt` | `pandas==2.2.3` para el gráfico de progreso. |
| `tests/test_sprint31.py` | **Nuevo:** 6 casos del harness. |

## Decisiones de diseño

- **Huérfanos:** se usa el esquema real `concept_id_a` / `concept_id_b` (no `source_id`/`target_id` del enunciado).
- **Semanas ISO:** etiqueta `YYYY-Www` alineada con `datetime.isocalendar()`.
- **Progreso acumulado:** por cada semana presente en los datos se emite una fila por categoría conocida del usuario, con conteo acumulado hasta esa semana (incluye categorías en 0 hasta su primera captura).

## Estado del proyecto

- La vista Conectar muestra brechas y envía al usuario a Descubrir con la pregunta sugerida.
- Dominar muestra evolución semanal por categoría con filtro.
- Telegram puede listar brechas con `/brechas`.
