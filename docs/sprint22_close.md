# Sprint 22 — Close: Migración a Supabase

## Resultado del harness

**281 passed, 0 regressions** (tests corren en modo SQLite; `conftest.py` fuerza `DATABASE_URL=""` para aislar la suite de cualquier BD remota).

---

## Items implementados

### 1. Detección dual de motor (`db/schema.py`)

- Nueva función `get_db_mode()` → retorna `'postgresql'` si `DATABASE_URL` está en el entorno, `'sqlite'` si no.
- Importación opcional de `psycopg2` con flag `_PSYCOPG2_AVAILABLE`; si no está instalado, el modo SQLite sigue funcionando sin error.
- Carga automática del `.env` vía `python-dotenv` (opcional, falla silenciosamente en CI).

### 2. Conexión robusta a PostgreSQL: `_pg_connect()` (`db/schema.py`)

- Parsea `DATABASE_URL` con `urllib.parse` (no con el parser interno de libpq) para manejar contraseñas con caracteres especiales (`@`, `:`, `/`, `[`, `]`) sin error.
- Sanitiza la URL antes de parsearla (elimina espacios, `\n` y BOM que Streamlit Cloud puede introducir al inyectar secrets multi-línea).
- Fuerza IPv4 en dos pasos:
  1. `socket.getaddrinfo(..., AF_INET)` → registro A del DNS del sistema.
  2. Fallback DNS-over-HTTPS (Google `8.8.8.8`) si el sistema no devuelve IPv4.
- Re-intenta automáticamente con el Transaction Pooler (puerto 6543) si el Session Pooler (5432) responde con `"Tenant or user not found"` (proyecto Supabase pausado).
- Añade `sslmode='require'` por defecto (Supabase lo exige).

### 3. Wrapper de cursor: `_PGCursor` (`db/schema.py`)

- Envuelve un cursor de psycopg2 con la interfaz de `sqlite3` (`.lastrowid`, `.fetchone()`, `.fetchall()`, `.rowcount`).
- `.lastrowid` se puebla capturando el resultado de `RETURNING id`, que `_NuraConn.execute()` agrega automáticamente a cada `INSERT`.

### 4. Conexión unificada: `_NuraConn` (`db/schema.py`)

- Context manager que abstrae SQLite y PostgreSQL con la misma interfaz.
- `execute(sql, params)` adapta placeholders `?` → `%s` en PostgreSQL.
- Re-lanza `psycopg2.IntegrityError` como `sqlite3.IntegrityError` para que `operations.py` capture un solo tipo de excepción.
- Commit al salir sin error; rollback si hay excepción; cierra la conexión siempre.

### 5. Inicialización del esquema: `init_db()` (`db/schema.py`)

- `_init_db_postgresql()`: DDL PostgreSQL con `SERIAL PRIMARY KEY`, `FLOAT`, y tres índices de rendimiento (`idx_concepts_user_id`, `idx_connections_user_id`, `idx_summaries_user_date`).
- `_init_db_sqlite()`: DDL SQLite sin cambios respecto a sprint anterior.
- Fallback automático: si la conexión PostgreSQL falla (red, credenciales, proyecto pausado), se activa `pg_fallback_active = True`, `DATABASE_URL` se vacía para la sesión, y la app continúa con SQLite.
- Banners de estado (`pg_fallback_active`, `pg_fallback_error`, `pg_debug_info`) disponibles para la UI.

### 6. Migraciones en PostgreSQL: `_run_migrations_postgresql()` (`db/schema.py`)

- Aplica todas las migraciones incrementales (Sprint 5–15) usando `ALTER TABLE … ADD COLUMN IF NOT EXISTS` (sintaxis disponible en PostgreSQL ≥ 9.6 y Supabase 15).
- Crea índices idempotentes con `CREATE INDEX IF NOT EXISTS`.
- No necesita recrear tablas (a diferencia de SQLite) porque PostgreSQL soporta modificación de constraints directamente.

### 7. Adaptador de queries: `_adapt_query()` (`db/operations.py`)

- Helper para construir queries dinámicas (cláusulas `SET`, etc.) que necesiten adaptar placeholders fuera del método `execute()`.
- `operations.py` sigue escribiendo `?` en todas sus queries; el adaptador convierte automáticamente según el motor.

### 8. Compatibilidad en `conftest.py` (`tests/conftest.py`)

- `os.environ["DATABASE_URL"] = ""` fijado al inicio del módulo, antes de que cualquier import llame a `load_dotenv()`.
- `python-dotenv` con `override=False` (default) respeta la variable ya existente → todos los tests corren en modo SQLite.

---

## Archivos modificados

| Archivo | Cambios |
|---|---|
| `db/schema.py` | Reescritura completa: `get_db_mode`, `_pg_connect`, `_PGCursor`, `_NuraConn`, `_init_db_postgresql`, `_run_migrations_postgresql`, fallback SQLite, banderas de diagnóstico |
| `db/operations.py` | Añadido `_adapt_query()`; importa `get_db_mode`; sin cambios en queries (compatibles con `?`) |
| `tests/conftest.py` | `DATABASE_URL=""` fijado para aislar suite de PostgreSQL |

---

## Notas de despliegue

- Agregar `DATABASE_URL` en los Secrets de Streamlit Cloud (`postgresql://user:pass@host:port/db`).
- Si la URL contiene caracteres especiales en la contraseña, el sistema los maneja vía `urllib.parse.unquote` — no es necesario codificarlos manualmente.
- `psycopg2-binary` debe incluirse en `requirements.txt` para el entorno de producción.
