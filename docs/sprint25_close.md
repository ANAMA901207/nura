# Sprint 25 — Close: Bot de Telegram con FastAPI

## Resultado del harness

**8/8 passed, 0 failed, 0 regressions**

Subset de regresión: `test_db` + `test_sprint23` + `test_sprint24` + `test_sprint25` → **26 passed** en 3.9 s.

---

## Items implementados

### 1. Migración BD — campos Telegram (`db/schema.py`)

Nueva lista `_SPRINT25_USER_MIGRATIONS`:
```python
("telegram_id",       "TEXT"),
("link_code",         "TEXT"),
("link_code_expiry",  "TEXT"),
```
- Añadida a `_init_db_postgresql`, `_run_migrations_postgresql` (`ADD COLUMN IF NOT EXISTS`) y `_run_migrations_sqlite` (`ALTER TABLE` idempotente con `try/except`).
- Campo `telegram_id`: ID de Telegram del usuario vinculado.
- Campo `link_code`: código temporal de vinculación (6 dígitos).
- Campo `link_code_expiry`: timestamp ISO de expiración (ahora + 10 min).

### 2. Cuatro funciones nuevas en `db/operations.py`

| Función | Descripción |
|---|---|
| `get_user_by_telegram_id(telegram_id)` | Busca usuario por telegram_id exacto |
| `set_telegram_id(user_id, telegram_id)` | Persiste la vinculación |
| `save_link_code(user_id, code, expiry)` | Guarda código + expiración |
| `get_user_by_link_code(code)` | Retorna User si el código es válido y no expiró; None si no |

### 3. `bot/nura_bridge.py` — puente Telegram ↔ Nura

- **`get_user_by_telegram_id(telegram_id)`** — delega a `db.operations`.
- **`generate_link_code(user_id)`** — genera 6 dígitos aleatorios, llama a `save_link_code` con expiración de 10 min, devuelve el código.
- **`link_user(telegram_id, link_code)`** — valida código vía `get_user_by_link_code`, llama a `set_telegram_id`, invalida el código usado.
- **`get_pending_concepts(user_id)`** — llama a `get_concepts_due_today`.
- **`run_tutor(user_id, mensaje)`** — carga perfil del usuario, invoca `build_graph()` con el mensaje y retorna la respuesta como string.

### 4. `bot/handlers.py` — lógica de comandos

Router `process_update(update: dict) → dict(chat_id, text, handled)`:

| Comando | Handler |
|---|---|
| `/start` | `handle_start` — saludo y menú, o instrucciones de vinculación si no está vinculado |
| `/capturar [término]` | `handle_capturar` — invoca tutor para capturar |
| `/repasar` | `handle_repasar` — lista hasta 10 conceptos pendientes SM-2 |
| `/streak` | `handle_streak` — racha + barra de progreso ASCII |
| `/meta [número]` | `handle_meta` — actualiza `daily_goal` |
| `/vincular [código]` | `handle_vincular` — llama a `link_user` |
| texto libre | `handle_free_message` — invoca tutor con contexto completo |
| usuario no vinculado | → `_msg_no_vinculado()` en todos los handlers que lo requieran |

Los handlers devuelven texto; el envío HTTP a Telegram lo hace `bot/main.py`.

### 5. `bot/main.py` — FastAPI app

- **GET `/health`** → `{"status": "ok"}` (200).
- **POST `/webhook`** → parsea JSON, llama a `process_update`, envía respuesta con `_send_message`.
- **Lifespan** (`@asynccontextmanager`) registra el webhook en Telegram al arrancar usando `TELEGRAM_TOKEN` y `WEBHOOK_URL` del entorno.  Si faltan, arranca sin registrar (seguro en CI/tests).
- **`_send_message`** — envía texto via `POST /sendMessage` con `parse_mode='Markdown'` y límite de 4096 caracteres.

### 6. Botón "Vincular Telegram" en `ui/app.py`

Nuevo expander **"Vincular Telegram"** en el sidebar (debajo de "Mi perfil"):
- Botón que llama a `generate_link_code(user_id)` y guarda el código en `session_state["_tg_link_code"]`.
- Muestra el comando listo para copiar: `st.code("/vincular XXXXXX")`.
- Texto explicativo: "El código expira en 10 minutos."

### 7. `Procfile` (Railway)

```
web: uvicorn bot.main:app --host 0.0.0.0 --port $PORT
```

### 8. Harness `tests/test_sprint25.py` (8 tests)

| Test | Descripción |
|---|---|
| `test_health_endpoint_returns_ok` | FastAPI TestClient: GET /health → 200 |
| `test_free_message_routes_to_tutor` | texto libre → `handle_free_message` → respuesta del tutor |
| `test_capturar_command_detected` | `/capturar LangGraph` → handler correcto invocado |
| `test_streak_command_detected` | `/streak` → respuesta con racha y progreso |
| `test_unlinked_user_gets_prompt` | telegram_id sin vincular → instrucciones de vinculación |
| `test_generate_link_code_six_digits` | código generado = 6 dígitos numéricos |
| `test_get_user_by_link_code_valid` | código vigente → retorna User |
| `test_get_user_by_link_code_expired` | código expirado → retorna None |

Todos los tests usan `unittest.mock` — sin red real ni BD compartida.

---

## Variables de entorno requeridas (producción)

| Variable | Descripción |
|---|---|
| `TELEGRAM_TOKEN` | Token del bot obtenido de @BotFather |
| `WEBHOOK_URL` | URL pública donde Telegram enviará los updates |
| `DATABASE_URL` | URL de Supabase (misma que la app Streamlit) |

---

## Archivos creados / modificados

| Archivo | Acción | Descripción |
|---|---|---|
| `bot/__init__.py` | Creado | Marca el directorio como paquete Python |
| `bot/main.py` | Creado | FastAPI app con /health, /webhook y lifespan |
| `bot/handlers.py` | Creado | Router y handlers de comandos |
| `bot/nura_bridge.py` | Creado | Puente a BD y agentes de Nura |
| `Procfile` | Creado | Comando de arranque para Railway |
| `db/schema.py` | Modificado | `_SPRINT25_USER_MIGRATIONS`; DDL users actualizado |
| `db/operations.py` | Modificado | 4 funciones Telegram |
| `ui/app.py` | Modificado | Expander "Vincular Telegram" en sidebar |
| `tests/test_sprint25.py` | Creado | Harness (8 tests) |
