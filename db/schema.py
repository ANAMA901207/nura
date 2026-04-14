"""
db/schema.py
============
Configuración de la conexión e inicialización del esquema de tablas.

Sprint 22: modo dual — usa PostgreSQL si DATABASE_URL está en el entorno,
o SQLite local si no lo está.  La interfaz pública es idéntica para ambos
motores; el código cliente en operations.py no necesita distinguir entre
ambos backends salvo para los placeholders (gestionados por _NuraConn).

Regla de selección de motor
----------------------------
    DATABASE_URL en entorno → PostgreSQL (Supabase o cualquier instancia PG)
    sin DATABASE_URL         → SQLite (archivo db/nura.db, por defecto en tests)
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

# ── Carga opcional del .env para detectar DATABASE_URL ───────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv es opcional en entornos CI sin archivo .env

# ── Importación opcional de psycopg2 ─────────────────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.errorcodes
    _PSYCOPG2_AVAILABLE = True
except ImportError:
    _PSYCOPG2_AVAILABLE = False

# ── Columnas de migraciones por sprint ───────────────────────────────────────

_SPRINT5_MIGRATIONS = [
    ("is_classified", "INTEGER NOT NULL DEFAULT 0"),
    ("user_context",  "TEXT    NOT NULL DEFAULT ''"),
]

_SPRINT7_MIGRATIONS = [
    ("consecutive_correct",   "INTEGER NOT NULL DEFAULT 0"),
    ("consecutive_incorrect",  "INTEGER NOT NULL DEFAULT 0"),
    ("total_reviews",          "INTEGER NOT NULL DEFAULT 0"),
    ("next_review",            "TEXT"),
]

_SPRINT8_MIGRATIONS = [
    ("sm2_interval", "REAL NOT NULL DEFAULT 1.0"),
    ("sm2_ef",       "REAL NOT NULL DEFAULT 2.5"),
]

_SPRINT11_CONCEPT_MIGRATIONS = [
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
]
_SPRINT11_CONNECTION_MIGRATIONS = [
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
]
_SPRINT11_SUMMARY_MIGRATIONS = [
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
]

_SPRINT15_USER_MIGRATIONS = [
    ("profession",    "TEXT NOT NULL DEFAULT ''"),
    ("learning_area", "TEXT NOT NULL DEFAULT ''"),
    ("tech_level",    "TEXT NOT NULL DEFAULT ''"),
]

# Ruta al archivo SQLite.  Sobreescribible desde tests para usar BDs temporales.
DB_PATH: Path = Path(__file__).parent / "nura.db"

# Bandera: True si init_db() intentó usar PostgreSQL pero cayó a SQLite.
# La UI de app.py la lee para mostrar un aviso al usuario.
pg_fallback_active: bool = False
pg_fallback_error: str = ""  # mensaje del error que causó el fallback


# ── Detección del motor activo ────────────────────────────────────────────────

def get_db_mode() -> str:
    """
    Retorna el motor de base de datos activo.

    Devuelve
    --------
    'postgresql' si DATABASE_URL está definida en el entorno, 'sqlite' si no.
    """
    return "postgresql" if os.environ.get("DATABASE_URL") else "sqlite"


def _pg_connect(**extra_kwargs):
    """
    Abre una conexión psycopg2 parseando DATABASE_URL en componentes individuales.

    Por qué no usar la URL directamente
    ------------------------------------
    psycopg2 parsea la URL con el parser estándar de libpq, que interpreta
    ciertos caracteres ([ ] @ : /) como delimitadores de la URL.  Si la
    contraseña contiene alguno de estos caracteres — habitual en Supabase
    y otros servicios que generan passwords aleatorias — el parser los
    interpreta mal y lanza OperationalError antes de intentar la conexión.

    La solución es parsear la URL con `urllib.parse` (que hace unquote del
    percent-encoding) y pasar host, port, user, password y dbname como
    kwargs separados.  Así psycopg2 no necesita tocar la contraseña.

    Parámetros SSL
    --------------
    Supabase exige SSL.  Añadimos sslmode='require' salvo que la URL
    ya declare otro valor explícito en su query string.
    """
    import socket
    import urllib.parse

    # Sanear ANTES de parsear: eliminar espacios, newlines o BOM accidentales.
    # Ocurre cuando el TOML de Streamlit Cloud rompe el valor en varias líneas,
    # resultando en un DATABASE_URL que empieza con '\n' y urlparse no reconoce.
    raw_url = os.environ.get("DATABASE_URL", "")
    url = raw_url.strip()

    # Loguear URL saneada (contraseña tapada) para diagnóstico.
    _url_safe = url.split("@")[-1] if "@" in url else url
    print(f"[Nura/_pg_connect] DATABASE_URL (sin credenciales): ...@{_url_safe}")

    if not url:
        raise RuntimeError(
            "DATABASE_URL está vacía. Verifica los Secrets de Streamlit Cloud."
        )

    parsed = urllib.parse.urlparse(url)

    # Parámetros del query string de la URL (ej. ?sslmode=require)
    qs: dict[str, str] = {
        k: v[0]
        for k, v in urllib.parse.parse_qs(parsed.query).items()
    }

    _host = parsed.hostname or "localhost"
    _user = urllib.parse.unquote(parsed.username or "")
    _dbname = (parsed.path or "/postgres").lstrip("/")
    _port = parsed.port or 5432

    # Forzar IPv4: Streamlit Cloud no admite conexiones IPv6 salientes.
    # Resolvemos el hostname y usamos el primer resultado IPv4 via `hostaddr`.
    _hostaddr: str | None = None
    try:
        ipv4_results = socket.getaddrinfo(
            _host, _port, socket.AF_INET, socket.SOCK_STREAM
        )
        if ipv4_results:
            _hostaddr = ipv4_results[0][4][0]
    except OSError:
        pass  # si falla la resolución, dejamos que psycopg2 lo intente

    # Log de diagnóstico (sin contraseña) para identificar problemas de URL.
    print(
        f"[Nura/_pg_connect] host={_host!r} port={_port} "
        f"user={_user!r} dbname={_dbname!r} "
        f"hostaddr(IPv4)={_hostaddr!r}"
    )

    params: dict = {
        "host":            _host,
        "port":            _port,
        "user":            _user,
        "password":        urllib.parse.unquote(parsed.password or ""),
        "dbname":          _dbname,
        "sslmode":         qs.get("sslmode", "require"),  # default: require
        "connect_timeout": int(qs.get("connect_timeout", "15")),
    }
    # `hostaddr` fuerza la IP concreta y evita que psycopg2 elija IPv6.
    if _hostaddr:
        params["hostaddr"] = _hostaddr
    params.update(extra_kwargs)

    # Intentar la conexión.  Si el Session Pooler (5432) devuelve
    # "Tenant or user not found" (proyecto pausado o pooler incorrecto)
    # reintentamos automáticamente con el Transaction Pooler (6543).
    try:
        return psycopg2.connect(**params)
    except psycopg2.OperationalError as _e:
        _msg = str(_e).lower()
        # Sólo reintentamos si el error es del pooler y el puerto era 5432.
        if "tenant or user not found" in _msg and params.get("port") == 5432:
            print(
                "[Nura/_pg_connect] Session pooler (5432) rechazó con "
                "'Tenant or user not found'. Reintentando con Transaction "
                "pooler (6543)…"
            )
            fallback_params = {**params, "port": 6543}
            # Resolver IPv4 para el mismo host pero puerto 6543.
            try:
                _res6543 = socket.getaddrinfo(
                    _host, 6543, socket.AF_INET, socket.SOCK_STREAM
                )
                if _res6543:
                    fallback_params["hostaddr"] = _res6543[0][4][0]
            except OSError:
                pass
            return psycopg2.connect(**fallback_params)
        raise


# ── Cursor wrapper para psycopg2 ──────────────────────────────────────────────

class _PGCursor:
    """
    Envuelve un cursor de psycopg2 con la interfaz de cursor de sqlite3.

    Añade la propiedad `lastrowid` que sqlite3 expone nativamente pero que
    psycopg2 no tiene (se puebla cuando _NuraConn.execute() detecta un INSERT).
    Las filas se exponen como dict-like gracias a RealDictCursor subyacente.
    """

    def __init__(self, cursor: Any, lastrowid: int | None = None) -> None:
        self._cur = cursor
        self._lastrowid = lastrowid

    # ── sqlite3 API parity ────────────────────────────────────────────────────

    @property
    def lastrowid(self) -> int | None:
        return self._lastrowid

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


# ── Conexión unificada ────────────────────────────────────────────────────────

class _NuraConn:
    """
    Conexión unificada que abstrae SQLite y PostgreSQL con la misma interfaz.

    Características
    ---------------
    - execute(sql, params): adapta placeholders '?' → '%s' en PostgreSQL y
      devuelve un cursor compatible con sqlite3 (con .lastrowid, .fetchone,
      .fetchall, .rowcount).
    - En INSERT statements (PostgreSQL), agrega automáticamente 'RETURNING id'
      para poblar cursor.lastrowid sin cambiar el código de operations.py.
    - Los errores de integridad de psycopg2 se re-lanzan como
      sqlite3.IntegrityError para que operations.py use un solo tipo de excepción.
    - Funciona como context manager: commit al salir sin error, rollback si hay
      excepción, cierra la conexión al finalizar.
    """

    def __init__(self) -> None:
        self._mode = get_db_mode()
        if self._mode == "postgresql":
            if not _PSYCOPG2_AVAILABLE:
                raise ImportError(
                    "psycopg2 no está instalado. "
                    "Ejecuta: pip install psycopg2-binary"
                )
            self._raw = _pg_connect(
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        else:
            self._raw = sqlite3.connect(str(DB_PATH))
            self._raw.execute("PRAGMA foreign_keys = ON")
            self._raw.row_factory = sqlite3.Row

    # ── Ejecución unificada ───────────────────────────────────────────────────

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        """
        Ejecuta una sentencia SQL con manejo automático de placeholders.

        Para PostgreSQL:
        - Convierte '?' a '%s'.
        - En INSERT, agrega 'RETURNING id' y puebla cursor.lastrowid.
        - Re-lanza IntegrityError de psycopg2 como sqlite3.IntegrityError.

        Para SQLite:
        - Delega directamente a conn.execute() (comportamiento original).
        """
        if self._mode == "postgresql":
            return self._pg_execute(sql, params)
        return self._raw.execute(sql, params)

    def _pg_execute(self, sql: str, params: tuple | list = ()) -> _PGCursor:
        adapted = sql.replace("?", "%s")
        is_insert = adapted.strip().upper().startswith("INSERT")
        needs_returning = is_insert and "RETURNING" not in adapted.upper()

        if needs_returning:
            adapted = adapted.rstrip().rstrip(";") + " RETURNING id"

        cur = self._raw.cursor()
        try:
            cur.execute(adapted, params if params else None)
        except Exception as e:
            if _PSYCOPG2_AVAILABLE and isinstance(e, psycopg2.IntegrityError):
                raise sqlite3.IntegrityError(str(e)) from e
            raise

        lastrowid = None
        if needs_returning:
            row = cur.fetchone()
            lastrowid = row["id"] if row else None

        return _PGCursor(cur, lastrowid=lastrowid)

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "_NuraConn":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        try:
            if exc_type is None:
                self._raw.commit()
            else:
                self._raw.rollback()
        except Exception:
            pass
        try:
            self._raw.close()
        except Exception:
            pass
        return False

    # ── Compatibilidad con código heredado (SQLite) ───────────────────────────

    def executescript(self, sql: str) -> None:
        """Ejecuta un script SQL multi-sentencia.  Solo para SQLite."""
        if self._mode == "sqlite":
            self._raw.executescript(sql)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


# ── API pública ───────────────────────────────────────────────────────────────

def get_connection() -> _NuraConn:
    """
    Abre y devuelve una conexión activa al motor de BD configurado.

    Modo SQLite (sin DATABASE_URL)
    ------------------------------
    - Conecta al archivo DB_PATH.
    - Activa PRAGMA foreign_keys = ON.
    - Usa row_factory = sqlite3.Row para acceso por nombre de columna.

    Modo PostgreSQL (con DATABASE_URL)
    -----------------------------------
    - Conecta a la URL de Supabase/PostgreSQL.
    - Usa RealDictCursor para acceso dict-like compatible con sqlite3.Row.

    Úsala con el context manager `with`:
        with get_connection() as conn:
            conn.execute(...)
    """
    return _NuraConn()


# ── Inicialización del esquema ────────────────────────────────────────────────

def init_db() -> None:
    """
    Crea las tablas de la base de datos si aún no existen (idempotente).

    Selecciona el DDL apropiado según el motor activo y luego aplica las
    migraciones incrementales para bases de datos existentes.

    Si DATABASE_URL está configurada pero la conexión PostgreSQL falla
    (proyecto pausado, credenciales incorrectas, red no disponible),
    registra la advertencia en consola y cae back a SQLite para que
    la aplicación siga funcionando.  El banner amarillo en la UI notifica
    al usuario de la situación.
    """
    if get_db_mode() == "postgresql":
        try:
            _init_db_postgresql()
        except Exception as _pg_err:  # noqa: BLE001
            import traceback as _tb
            global pg_fallback_active, pg_fallback_error
            pg_fallback_active = True
            pg_fallback_error = (
                f"{type(_pg_err).__name__}: {_pg_err}"
            )
            # Desactivar PostgreSQL para el resto de la sesión y usar SQLite.
            # get_db_mode() y get_connection() también quedarán en modo SQLite.
            os.environ["DATABASE_URL"] = ""
            print(
                "[Nura] ═══ ERROR POSTGRESQL — usando SQLite como fallback ═══\n"
                f"Tipo : {type(_pg_err).__name__}\n"
                f"Causa: {_pg_err}\n"
                f"Traza:\n{_tb.format_exc()}"
            )
            _init_db_sqlite()
    else:
        _init_db_sqlite()
    _run_migrations()


def _init_db_sqlite() -> None:
    """Inicializa el esquema en SQLite usando executescript."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS concepts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                term             TEXT    NOT NULL,
                category         TEXT    NOT NULL DEFAULT '',
                subcategory      TEXT    NOT NULL DEFAULT '',
                explanation      TEXT    NOT NULL DEFAULT '',
                examples         TEXT    NOT NULL DEFAULT '',
                analogy          TEXT    NOT NULL DEFAULT '',
                context          TEXT    NOT NULL DEFAULT '',
                flashcard_front  TEXT    NOT NULL DEFAULT '',
                flashcard_back   TEXT    NOT NULL DEFAULT '',
                mastery_level    INTEGER NOT NULL DEFAULT 0
                                         CHECK (mastery_level BETWEEN 0 AND 5),
                created_at       TEXT    NOT NULL,
                last_reviewed         TEXT,
                is_classified         INTEGER NOT NULL DEFAULT 0,
                user_context          TEXT    NOT NULL DEFAULT '',
                consecutive_correct   INTEGER NOT NULL DEFAULT 0,
                consecutive_incorrect INTEGER NOT NULL DEFAULT 0,
                total_reviews         INTEGER NOT NULL DEFAULT 0,
                next_review           TEXT,
                sm2_interval          REAL    NOT NULL DEFAULT 1.0,
                sm2_ef                REAL    NOT NULL DEFAULT 2.5,
                user_id               INTEGER NOT NULL DEFAULT 0,
                UNIQUE(term, user_id)
            );

            CREATE TABLE IF NOT EXISTS connections (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                concept_id_a  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                concept_id_b  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                relationship  TEXT    NOT NULL DEFAULT '',
                created_at    TEXT    NOT NULL,
                user_id       INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS daily_summaries (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                date              TEXT    NOT NULL,
                concepts_captured INTEGER NOT NULL DEFAULT 0,
                new_connections   INTEGER NOT NULL DEFAULT 0,
                concepts_reviewed INTEGER NOT NULL DEFAULT 0,
                user_id           INTEGER NOT NULL DEFAULT 1,
                UNIQUE(date, user_id)
            );
        """)


def _init_db_postgresql() -> None:
    """
    Inicializa el esquema en PostgreSQL (Supabase).

    Sintaxis PostgreSQL usada — diferencias clave respecto a SQLite:
    ─────────────────────────────────────────────────────────────────
    • SERIAL PRIMARY KEY          ← auto-increment de PG (no AUTOINCREMENT)
    • FLOAT                       ← float8; REAL en SQLite es float4
    • TEXT NOT NULL DEFAULT ''    ← igual en ambos motores
    • CHECK, UNIQUE, REFERENCES   ← igual en ambos motores
    • CREATE INDEX IF NOT EXISTS  ← disponible en PG 9.5+; Supabase usa PG 15
    ─────────────────────────────────────────────────────────────────
    No uses AUTOINCREMENT aquí — es sintaxis exclusiva de SQLite y
    provoca psycopg2.ProgrammingError al ejecutar el DDL en PostgreSQL.
    """
    raw = _pg_connect()
    try:
        with raw.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    profession    TEXT NOT NULL DEFAULT '',
                    learning_area TEXT NOT NULL DEFAULT '',
                    tech_level    TEXT NOT NULL DEFAULT ''
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id               SERIAL PRIMARY KEY,
                    term             TEXT NOT NULL,
                    category         TEXT NOT NULL DEFAULT '',
                    subcategory      TEXT NOT NULL DEFAULT '',
                    explanation      TEXT NOT NULL DEFAULT '',
                    examples         TEXT NOT NULL DEFAULT '',
                    analogy          TEXT NOT NULL DEFAULT '',
                    context          TEXT NOT NULL DEFAULT '',
                    flashcard_front  TEXT NOT NULL DEFAULT '',
                    flashcard_back   TEXT NOT NULL DEFAULT '',
                    mastery_level    INTEGER NOT NULL DEFAULT 0
                                             CHECK (mastery_level BETWEEN 0 AND 5),
                    created_at       TEXT NOT NULL,
                    last_reviewed         TEXT,
                    is_classified         INTEGER NOT NULL DEFAULT 0,
                    user_context          TEXT NOT NULL DEFAULT '',
                    consecutive_correct   INTEGER NOT NULL DEFAULT 0,
                    consecutive_incorrect INTEGER NOT NULL DEFAULT 0,
                    total_reviews         INTEGER NOT NULL DEFAULT 0,
                    next_review           TEXT,
                    sm2_interval          FLOAT NOT NULL DEFAULT 1.0,
                    sm2_ef                FLOAT NOT NULL DEFAULT 2.5,
                    user_id               INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(term, user_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS connections (
                    id            SERIAL PRIMARY KEY,
                    concept_id_a  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                    concept_id_b  INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                    relationship  TEXT NOT NULL DEFAULT '',
                    created_at    TEXT NOT NULL,
                    user_id       INTEGER NOT NULL DEFAULT 1
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_summaries (
                    id                SERIAL PRIMARY KEY,
                    date              TEXT NOT NULL,
                    concepts_captured INTEGER NOT NULL DEFAULT 0,
                    new_connections   INTEGER NOT NULL DEFAULT 0,
                    concepts_reviewed INTEGER NOT NULL DEFAULT 0,
                    user_id           INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(date, user_id)
                )
            """)
            # Índices de rendimiento
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_concepts_user_id ON concepts(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_connections_user_id ON connections(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_user_date "
                "ON daily_summaries(user_id, date)"
            )
        raw.commit()
    finally:
        raw.close()


# ── Migraciones incrementales ─────────────────────────────────────────────────

def _run_migrations() -> None:
    """Despacha las migraciones al motor correcto."""
    if get_db_mode() == "postgresql":
        _run_migrations_postgresql()
    else:
        _run_migrations_sqlite()


def _run_migrations_postgresql() -> None:
    """
    Aplica migraciones en PostgreSQL usando ADD COLUMN IF NOT EXISTS (PG 9.6+).

    Supabase ejecuta PostgreSQL 15, por lo que esta sintaxis siempre está
    disponible.  No necesita recrear tablas como SQLite porque PostgreSQL
    soporta modificación de constraints directamente.
    """
    raw = _pg_connect()
    try:
        with raw.cursor() as cur:
            all_concept_cols = (
                _SPRINT5_MIGRATIONS
                + _SPRINT7_MIGRATIONS
                + _SPRINT8_MIGRATIONS
                + _SPRINT11_CONCEPT_MIGRATIONS
            )
            for col, defn in all_concept_cols:
                cur.execute(
                    f"ALTER TABLE concepts ADD COLUMN IF NOT EXISTS {col} {defn}"
                )
            for col, defn in _SPRINT11_CONNECTION_MIGRATIONS:
                cur.execute(
                    f"ALTER TABLE connections ADD COLUMN IF NOT EXISTS {col} {defn}"
                )
            for col, defn in _SPRINT11_SUMMARY_MIGRATIONS:
                cur.execute(
                    f"ALTER TABLE daily_summaries ADD COLUMN IF NOT EXISTS {col} {defn}"
                )
            for col, defn in _SPRINT15_USER_MIGRATIONS:
                cur.execute(
                    f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {defn}"
                )
            # Índices (idempotentes por IF NOT EXISTS)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_concepts_user_id ON concepts(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_connections_user_id ON connections(user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_user_date "
                "ON daily_summaries(user_id, date)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS uq_daily_date_user "
                "ON daily_summaries(date, user_id)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS uq_concepts_term_user "
                "ON concepts(term, user_id)"
            )
        raw.commit()
    finally:
        raw.close()


def _run_migrations_sqlite() -> None:
    """
    Aplica migraciones de esquema incrementales en SQLite de forma idempotente.

    Cada entrada de los bloques _SPRINTn_MIGRATIONS intenta añadir una columna
    nueva a la tabla correspondiente.  Si la columna ya existe (OperationalError),
    la ignora silenciosamente para que init_db() sea segura de llamar varias veces.

    Sprint 11 también crea la tabla users si no existe (seguro por IF NOT EXISTS)
    y agrega los índices de rendimiento para user_id.
    """
    conn = sqlite3.connect(str(DB_PATH))
    try:
        # ── Sprint 5-8: columnas en concepts ──────────────────────────────────
        concept_migrations = (
            _SPRINT5_MIGRATIONS
            + _SPRINT7_MIGRATIONS
            + _SPRINT8_MIGRATIONS
            + _SPRINT11_CONCEPT_MIGRATIONS
        )
        for col, definition in concept_migrations:
            try:
                conn.execute(f"ALTER TABLE concepts ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

        # ── Sprint 11: user_id en connections y daily_summaries ───────────────
        for col, definition in _SPRINT11_CONNECTION_MIGRATIONS:
            try:
                conn.execute(f"ALTER TABLE connections ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

        for col, definition in _SPRINT11_SUMMARY_MIGRATIONS:
            try:
                conn.execute(f"ALTER TABLE daily_summaries ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

        # ── Sprint 11: tabla users ─────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL
            )
        """)

        # ── Sprint 15: perfil de onboarding en users ─────────────────────────
        for col, definition in _SPRINT15_USER_MIGRATIONS:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

        # ── Sprint 11: índices de rendimiento ────────────────────────────────
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_concepts_user_id ON concepts(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_connections_user_id ON connections(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_summaries_user_date "
            "ON daily_summaries(user_id, date)"
        )

        # ── Sprint 11: reasignar data huérfana (user_id=1 sin dueño real) ────
        owner_exists = conn.execute(
            "SELECT 1 FROM users WHERE id = 1"
        ).fetchone()
        if owner_exists is None:
            conn.execute("UPDATE concepts        SET user_id = 0 WHERE user_id = 1")
            conn.execute("UPDATE connections     SET user_id = 0 WHERE user_id = 1")
            conn.execute("UPDATE daily_summaries SET user_id = 0 WHERE user_id = 1")

        conn.commit()

        # ── Sprint 11b: UNIQUE(date) → UNIQUE(date, user_id) en daily_summaries
        needs_unique_migration = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='index' AND name='uq_daily_date_user'"
        ).fetchone() is None

        if needs_unique_migration:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS daily_summaries_new (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    date              TEXT    NOT NULL,
                    concepts_captured INTEGER NOT NULL DEFAULT 0,
                    new_connections   INTEGER NOT NULL DEFAULT 0,
                    concepts_reviewed INTEGER NOT NULL DEFAULT 0,
                    user_id           INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(date, user_id)
                );
                INSERT OR IGNORE INTO daily_summaries_new
                    (id, date, concepts_captured, new_connections,
                     concepts_reviewed, user_id)
                    SELECT id, date, concepts_captured, new_connections,
                           concepts_reviewed, user_id
                    FROM daily_summaries;
                DROP TABLE daily_summaries;
                ALTER TABLE daily_summaries_new RENAME TO daily_summaries;
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS uq_daily_date_user "
                "ON daily_summaries(date, user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_user_date "
                "ON daily_summaries(user_id, date)"
            )
            conn.commit()

        # ── Migración: UNIQUE(term) → UNIQUE(term, user_id) en concepts ──────
        needs_concepts_unique_migration = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='index' AND name='uq_concepts_term_user'"
        ).fetchone() is None

        if needs_concepts_unique_migration:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS concepts_new (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    term             TEXT    NOT NULL,
                    category         TEXT    NOT NULL DEFAULT '',
                    subcategory      TEXT    NOT NULL DEFAULT '',
                    explanation      TEXT    NOT NULL DEFAULT '',
                    examples         TEXT    NOT NULL DEFAULT '',
                    analogy          TEXT    NOT NULL DEFAULT '',
                    context          TEXT    NOT NULL DEFAULT '',
                    flashcard_front  TEXT    NOT NULL DEFAULT '',
                    flashcard_back   TEXT    NOT NULL DEFAULT '',
                    mastery_level    INTEGER NOT NULL DEFAULT 0
                                             CHECK (mastery_level BETWEEN 0 AND 5),
                    created_at       TEXT    NOT NULL,
                    last_reviewed         TEXT,
                    is_classified         INTEGER NOT NULL DEFAULT 0,
                    user_context          TEXT    NOT NULL DEFAULT '',
                    consecutive_correct   INTEGER NOT NULL DEFAULT 0,
                    consecutive_incorrect INTEGER NOT NULL DEFAULT 0,
                    total_reviews         INTEGER NOT NULL DEFAULT 0,
                    next_review           TEXT,
                    sm2_interval          REAL    NOT NULL DEFAULT 1.0,
                    sm2_ef                REAL    NOT NULL DEFAULT 2.5,
                    user_id               INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(term, user_id)
                );
                INSERT OR IGNORE INTO concepts_new (
                    id, term, category, subcategory, explanation, examples,
                    analogy, context, flashcard_front, flashcard_back,
                    mastery_level, created_at, last_reviewed, is_classified,
                    user_context, consecutive_correct, consecutive_incorrect,
                    total_reviews, next_review, sm2_interval, sm2_ef, user_id
                )
                SELECT
                    id, term, category, subcategory, explanation, examples,
                    analogy, context, flashcard_front, flashcard_back,
                    mastery_level, created_at, last_reviewed, is_classified,
                    user_context, consecutive_correct, consecutive_incorrect,
                    total_reviews, next_review, sm2_interval, sm2_ef, user_id
                FROM concepts;
                DROP TABLE concepts;
                ALTER TABLE concepts_new RENAME TO concepts;
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS uq_concepts_term_user "
                "ON concepts(term, user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_concepts_user_id "
                "ON concepts(user_id)"
            )
            conn.commit()

    finally:
        conn.close()
