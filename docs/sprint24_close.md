# Sprint 24 — Close: Streak y meta diaria

## Resultado del harness

**7/7 passed** (harness sprint24).  
Subset de regresión: `test_db` + `test_bugfixes` + `test_sprint21` + `test_sprint23` + `test_sprint24` → **68 passed, 0 regressions** en 27 s.

---

## Items implementados

### 1. Migración `daily_goal` en la tabla `users` (`db/schema.py`)

- Nueva lista `_SPRINT24_USER_MIGRATIONS`: `("daily_goal", "INTEGER NOT NULL DEFAULT 3")`.
- **PostgreSQL** (`_init_db_postgresql`): columna incluida en el DDL inicial; `_run_migrations_postgresql` la añade con `ADD COLUMN IF NOT EXISTS` para BDs existentes.
- **SQLite** (`_init_db_sqlite`): columna incluida en el DDL del `CREATE TABLE IF NOT EXISTS users`; `_run_migrations_sqlite` la añade con `ALTER TABLE` en bloque `try/except OperationalError` (idempotente).

### 2. Campo `daily_goal` en el dataclass `User` (`db/models.py`)

```python
daily_goal: int = 3   # Sprint 24: meta de conceptos por día
```

Default `3` garantiza compatibilidad hacia atrás con objetos `User` de BDs sin migrar.

### 3. Cuatro funciones nuevas en `db/operations.py`

#### `get_streak(user_id=1) → int`

Reescritura basada en `concepts.created_at` (antes usaba `daily_summaries`):
- Itera hacia atrás desde hoy hasta 730 días.
- Para cada fecha cuenta `SELECT COUNT(*) FROM concepts WHERE user_id = ? AND SUBSTR(created_at, 1, 10) = ?`.
- Detiene el conteo al primer día sin concepto.
- Retorna 0 para usuario sin conceptos (backward compatible con `test_get_streak_empty_db`).

#### `get_today_count(user_id=1) → int`

- Cuenta conceptos con `SUBSTR(created_at, 1, 10) = date.today().isoformat()` para el usuario dado.

#### `get_daily_goal(user_id=1) → int`

- Lee `daily_goal` de `users WHERE id = ?`.
- Retorna `3` como fallback si el usuario no existe o la columna no está disponible (BD sin migrar).

#### `update_daily_goal(user_id, goal) → None`

- Recorta el valor al rango `[1, 50]` antes de persistir.
- Lanza `ValueError` si el usuario no existe.
- Usa `UPDATE users SET daily_goal = ? WHERE id = ?` con parámetros seguros.

También actualizado: `_row_to_user()` lee `daily_goal` con comprobación de clave (compatible con BDs sin migrar).

### 4. `render_streak(streak, today, goal)` (`ui/components.py`)

- Card HTML con 🔥 y el número de días consecutivos en naranja (`#fab387`).
- `st.progress(min(today/goal, 1.0), text="X de Y conceptos hoy")` nativo de Streamlit.
- `goal` se recorta a `max(1, goal)` internamente para evitar división por cero.

### 5. Integración en `ui/app.py`

**Vista Descubrir** — al inicio, antes del formulario de captura:
```python
render_streak(
    streak=get_streak(_uid_desc),
    today=get_today_count(_uid_desc),
    goal=get_daily_goal(_uid_desc),
)
```

**Tras captura exitosa** — toast si se alcanzó la meta:
```python
if get_today_count(_uid_after) >= get_daily_goal(_uid_after):
    st.toast("¡Meta del día cumplida! 🔥")
```

**Sidebar → Mi perfil** — `st.number_input` para cambiar la meta:
```python
_new_goal = st.number_input("Meta diaria de conceptos", min_value=1, max_value=50, ...)
# Al guardar:
update_daily_goal(_uid_sidebar, int(_new_goal))
```

Imports añadidos: `get_daily_goal`, `get_today_count`, `update_daily_goal`, `render_streak`.

### 6. Harness `tests/test_sprint24.py` (7 tests)

| Test | Descripción |
|---|---|
| `test_streak_zero_new_user` | Usuario sin conceptos → `get_streak` = 0 |
| `test_streak_one_day` | Concepto solo hoy → `get_streak` = 1 |
| `test_streak_consecutive_days` | Conceptos en 3 días seguidos → `get_streak` = 3 |
| `test_streak_broken` | Gap ayer → streak cuenta solo desde hoy = 1 |
| `test_today_count` | 2 conceptos de hoy + 1 de ayer → `get_today_count` = 2 |
| `test_daily_goal_default` | Usuario nuevo → `get_daily_goal` = 3 |
| `test_update_daily_goal` | `update_daily_goal(5)` → `get_daily_goal` = 5 |

Fixture `tmp_db`: BD SQLite temporal por test (`tmp_path`), aísla completamente cada caso.

---

## Archivos modificados

| Archivo | Cambios |
|---|---|
| `db/schema.py` | `_SPRINT24_USER_MIGRATIONS`; `daily_goal` en DDL SQLite y PostgreSQL; migraciones en `_run_migrations_sqlite` y `_run_migrations_postgresql` |
| `db/models.py` | Campo `daily_goal: int = 3` en `User` |
| `db/operations.py` | `_row_to_user` lee `daily_goal`; `get_streak` reescrito (concepts); `get_today_count`, `get_daily_goal`, `update_daily_goal` nuevas |
| `ui/components.py` | `render_streak(streak, today, goal)` |
| `ui/app.py` | Imports nuevos; `render_streak` en Descubrir; toast en meta; `number_input` + `update_daily_goal` en Mi perfil |
| `tests/test_sprint24.py` | Nuevo harness (7 tests) |
