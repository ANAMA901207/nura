# Sprint 26 Close — Alertas automáticas por Telegram

## Resultado del harness

```
6 passed, 0 failed, 0 regressions
26 passed total (sprints 23–26)
```

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `db/models.py` | Añadidos campos `telegram_id`, `link_code`, `link_code_expiry` (Sprint 25, faltaban en el dataclass) y `reminder_time: str = "20:00"` (Sprint 26) al dataclass `User` |
| `db/schema.py` | Añadido `_SPRINT26_USER_MIGRATIONS` con `reminder_time TEXT NOT NULL DEFAULT '20:00'`; migración idempotente para PostgreSQL (`ADD COLUMN IF NOT EXISTS`) y SQLite (`try/except OperationalError`); DDL actualizado para ambos motores |
| `db/operations.py` | Actualizado `_row_to_user` para leer `telegram_id`, `link_code`, `link_code_expiry` y `reminder_time` con comprobación de clave (compatibilidad retroactiva); añadidas tres funciones nuevas: `get_reminder_time`, `set_reminder_time`, `get_users_to_remind` |
| `bot/scheduler.py` | **Nuevo archivo.** `run_scheduler()`: loop async infinito (60 s) que consulta `get_users_to_remind`, construye mensaje con nombre + today_count + daily_goal + pending y lo envía por Telegram via `httpx`. Errores por usuario son capturados para no detener el loop |
| `bot/main.py` | `_lifespan` lanza `asyncio.create_task(run_scheduler())` después de registrar el webhook |
| `bot/handlers.py` | Añadido `handle_recordatorio(telegram_id, time_str)` y su despacho en `process_update` para el comando `/recordatorio HH:MM` |
| `ui/app.py` | Importados `get_reminder_time` y `set_reminder_time`; añadido `st.time_input` en el formulario "Mi perfil" del sidebar; hora se guarda con `set_reminder_time` al hacer submit |
| `tests/test_sprint26.py` | **Nuevo archivo.** 6 casos: `test_get_reminder_time_default`, `test_set_reminder_time`, `test_set_reminder_time_invalid`, `test_get_users_to_remind_matches_time`, `test_get_users_to_remind_excludes_completed`, `test_reminder_message_format` |

## Decisiones de diseño

### `get_reminder_time` con doble acceso a fila
`_NuraConn` expone las filas de SQLite como `sqlite3.Row` (dict-like via `row.keys()`),
pero la query `SELECT reminder_time FROM users WHERE id = ?` devuelve una única columna.
Se usa `row[0]` como fallback para modos en que `row.keys()` no está disponible,
garantizando compatibilidad con cualquier cursor.

### `get_users_to_remind` con subconsulta correlacionada
En lugar de cargar todos los conceptos en Python, se usa una subconsulta SQL
(`SELECT COUNT(*) FROM concepts WHERE user_id = u.id AND SUBSTR(created_at,1,10) = ?`)
para filtrar directamente en la BD. Funciona en SQLite y PostgreSQL.

### Scheduler dentro del proceso FastAPI
El scheduler corre como `asyncio.create_task` dentro del lifespan de FastAPI,
sin necesidad de un proceso externo ni Celery. Esto simplifica el despliegue en Railway
donde solo hay un proceso web definido en el `Procfile`.

### Manejo de errores en el scheduler
Si el envío a un usuario falla (red, token inválido, etc.), el error se registra en
consola y el loop continúa con los demás usuarios. Nunca se interrumpe el loop completo
por un fallo individual.

## Estado del proyecto

- **Recordatorios diarios** completamente implementados: configurables desde Streamlit,
  desde Telegram (`/recordatorio HH:MM`) y disparados automáticamente por el scheduler.
- **Bot de Telegram** (Sprints 25–26): webhook async sin timeouts, comandos vinculados a
  la cuenta Nura, scheduler de alertas corriendo en background.
- **Suite de tests**: 26 passed (sprints 23–26), sin regresiones.
- **Próximos pasos sugeridos**: celebración de meta (toast + mensaje Telegram cuando se
  completan los conceptos del día), analytics de recordatorios enviados.
