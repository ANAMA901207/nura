# Sprint 26 — Alertas automáticas por Telegram

## Objetivo
Nura te busca a ti — envía alertas diarias por Telegram
sin que el usuario tenga que abrir la app.

## Alertas
1. **Recordatorio diario** — si el usuario no ha capturado
   ningún concepto hoy, Nura le escribe a la hora configurada
2. **Conceptos pendientes** — si tiene conceptos vencidos
   según SM-2, los menciona en el recordatorio
3. **Celebración de meta** — cuando completa su meta diaria,
   Nura le felicita por Telegram

## Configuración por usuario
- Cada usuario configura su hora de recordatorio (default 20:00)
- Se guarda en BD como `reminder_time TEXT` (formato "HH:MM")
- Configurable desde la app Streamlit en "Mi perfil"
- También configurable desde Telegram con `/recordatorio HH:MM`

## Arquitectura
- Scheduler corre dentro del mismo proceso FastAPI en Railway
- Usa `asyncio` con un loop que verifica cada minuto
- Al arrancar el bot, inicia el scheduler en background
- El scheduler consulta BD y envía mensajes a usuarios
  que cumplen la condición

## Archivos a modificar
- `db/schema.py` — campo `reminder_time TEXT DEFAULT '20:00'`
  en tabla users
- `db/operations.py` — funciones:
  `get_reminder_time(user_id) -> str`
  `set_reminder_time(user_id, time_str) -> None`
  `get_users_to_remind(current_time_str) -> list[User]`
- `bot/scheduler.py` — nuevo archivo con el loop de alertas
- `bot/main.py` — iniciar scheduler en lifespan
- `bot/handlers.py` — comando `/recordatorio HH:MM`
- `ui/app.py` — input de hora en "Mi perfil"

## Comportamiento esperado
- A las 20:00 (o la hora configurada), si el usuario
  no capturó nada hoy → Nura le escribe por Telegram
- Si tiene conceptos pendientes → los menciona
- Si ya cumplió su meta → no envía recordatorio
- Formato del mensaje:
  "🌙 Hey [nombre], hoy llevas X conceptos.
   Tienes Y conceptos pendientes de repasar.
   ¿Le dedicamos 5 minutos?"

## Harness
- `test_get_reminder_time_default` → retorna "20:00"
- `test_set_reminder_time` → persiste hora correctamente
- `test_get_users_to_remind_matches_time` → retorna usuarios
  cuya hora coincide con la actual y no han cumplido meta
- `test_get_users_to_remind_excludes_completed` → excluye
  usuarios que ya cumplieron su meta hoy
- `test_reminder_message_format` → mensaje tiene nombre
  y datos correctos
- `test_invalid_time_format_rejected` → "25:00" → error

## Reglas
- Solo alertar usuarios con telegram_id vinculado
- No alertar si el usuario ya cumplió su meta
- No tocar agentes ni tests existentes
- Correr pytest al cerrar y crear sprint26_close.md