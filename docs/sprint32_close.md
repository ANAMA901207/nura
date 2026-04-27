# Sprint 32 Close — Perfil de aprendizaje visible

## Resultado del harness

```
tests/test_sprint32.py: 7 passed, 0 failed
Suite completa tests/: 352 passed, 3 failed (355 tests)
```

Los 3 fallos son los habituales por llamadas reales a Gemini (`test_agents.py` ×2, `test_sprint4.py::test_tutor_uses_bd_context`), no por el Sprint 32.

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `db/operations.py` | `get_max_streak`, `get_activity_last_30_days`, `get_user_stats` (métricas, top 3 categorías, rachas, certificaciones aprobadas, `mastery_pct` por nivel ≥4 entre clasificados). |
| `ui/components.py` | `render_profile(stats)` y `render_activity_heatmap(activity_data)` (pandas + `st.bar_chart`). |
| `ui/app.py` | Vista `perfil` en URL y sidebar («👤 Mi perfil»), `_render_view_perfil`, formulario de meta diaria y recordatorio. |
| `bot/handlers.py` | `/perfil` → `handle_perfil`, texto formateado; mención en `/start`. |
| `tests/test_sprint32.py` | **Nuevo:** 7 casos del harness. |

## Decisiones de diseño

- **Racha máxima:** días de calendario consecutivos con al menos una captura (`DISTINCT` fecha en `created_at`), alineado con la lógica de `get_streak`.
- **Actividad 30 días:** 30 filas fijas (hoy − 29 … hoy), `count` puede ser 0.
- **`mastery_pct`:** entre conceptos con `is_classified = 1`, porcentaje con `mastery_level >= 4`.
- **Mensaje motivacional en perfil:** si `total_concepts < 5`, `render_profile` muestra el `st.info` y no el bloque completo de métricas.
- **Onboarding:** sigue en el expander lateral; la vista Mi perfil enlaza a ese expander para profesión/áreas/nivel.

## Estado del proyecto

- El usuario tiene una vista dedicada de perfil con estadísticas, gráfico de actividad y ajustes rápidos.
- Telegram ofrece resumen con `/perfil`.
