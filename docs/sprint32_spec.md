# Sprint 32 — Perfil de aprendizaje visible

## Objetivo
Una página que muestre la "huella de conocimiento"
del usuario — algo que dé orgullo ver y compartir.

## Contenido del perfil
1. **Resumen de conocimiento**
   - Total de conceptos capturados
   - Total de conexiones en el mapa
   - Categorías más fuertes (top 3)
   - Racha actual y racha máxima histórica

2. **Certificaciones obtenidas**
   - Lista de categorías certificadas con fecha y puntaje
   - Badge visual por cada una

3. **Estadísticas de dominio**
   - % de conceptos dominados vs pendientes
   - Distribución por categoría (gráfica de torta o barras)

4. **Actividad reciente**
   - Últimos 7 días de actividad
   - Heatmap estilo GitHub (días activos vs inactivos)

## Acceso
- Nueva vista "👤 Mi perfil" en el menú de Streamlit
- En Telegram → `/perfil` muestra versión texto

## Archivos a modificar
- `db/operations.py` — función:
  `get_user_stats(user_id) -> dict` — consolida
  todas las estadísticas del usuario
  `get_max_streak(user_id) -> int`
  `get_activity_last_30_days(user_id) -> list[dict]`
- `ui/app.py` — nueva vista "Mi perfil"
- `ui/components.py` — `render_profile(stats)`
  `render_activity_heatmap(activity_data)`
- `bot/handlers.py` — `/perfil`

## Harness
- `test_get_user_stats_structure`
- `test_get_max_streak_empty`
- `test_get_max_streak_with_data`
- `test_get_activity_last_30_days`
- `test_perfil_command_telegram`
- `test_render_profile_no_crash`

## Reglas
- Si el usuario es nuevo (pocos conceptos) →
  mensaje motivacional en lugar de stats vacías
- No romper tests existentes
- Correr pytest al cerrar y crear sprint32_close.md