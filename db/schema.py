"""
db/schema.py
============
Configuración de la conexión SQLite e inicialización del esquema de tablas.

Este módulo es el único punto de contacto con el archivo físico de la base
de datos.  Todas las funciones en operations.py llaman a get_connection()
para obtener una conexión; nunca abren el archivo directamente.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Columnas añadidas en sprints anteriores.  Se migran automáticamente en init_db()
# para bases de datos existentes creadas antes de estas versiones.
_SPRINT5_MIGRATIONS = [
    ("is_classified", "INTEGER NOT NULL DEFAULT 0"),
    ("user_context",  "TEXT    NOT NULL DEFAULT ''"),
]

_SPRINT7_MIGRATIONS = [
    ("consecutive_correct",   "INTEGER NOT NULL DEFAULT 0"),
    ("consecutive_incorrect",  "INTEGER NOT NULL DEFAULT 0"),
    ("total_reviews",          "INTEGER NOT NULL DEFAULT 0"),
    ("next_review",            "TEXT"),   # nullable ISO 8601, NULL = sin programar
]

# Columnas del algoritmo SM-2 añadidas en Sprint 8.
_SPRINT8_MIGRATIONS = [
    ("sm2_interval", "REAL NOT NULL DEFAULT 1.0"),  # días hasta próximo repaso (float)
    ("sm2_ef",       "REAL NOT NULL DEFAULT 2.5"),  # Easiness Factor; mínimo 1.3
]

# Sprint 11: columna user_id en las tres tablas de datos para aislar datos por usuario.
# DEFAULT 0 reserva el user_id=0 como "legacy" — ningún usuario real tendrá ese ID
# porque SQLite AUTOINCREMENT comienza en 1.  Esto evita que el primer usuario
# registrado (id=1) vea datos históricos de antes de la migración multi-usuario.
_SPRINT11_CONCEPT_MIGRATIONS = [
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
]
_SPRINT11_CONNECTION_MIGRATIONS = [
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
]
_SPRINT11_SUMMARY_MIGRATIONS = [
    ("user_id", "INTEGER NOT NULL DEFAULT 0"),
]

# Sprint 15: campos de perfil de onboarding en la tabla users.
# DEFAULT '' garantiza que usuarios existentes no rompan al leer la columna.
_SPRINT15_USER_MIGRATIONS = [
    ("profession",    "TEXT NOT NULL DEFAULT ''"),
    ("learning_area", "TEXT NOT NULL DEFAULT ''"),
    ("tech_level",    "TEXT NOT NULL DEFAULT ''"),
]

# Ruta al archivo de la base de datos, ubicado en la misma carpeta que este módulo.
# Se puede sobreescribir desde los tests para usar una BD temporal aislada.
DB_PATH: Path = Path(__file__).parent / "nura.db"


def get_connection() -> sqlite3.Connection:
    """
    Abre y devuelve una conexión activa a la base de datos SQLite.

    Configuraciones aplicadas en cada conexión:
    - PRAGMA foreign_keys = ON  → activa el cumplimiento de claves foráneas,
      que SQLite desactiva por defecto por compatibilidad histórica.
    - row_factory = sqlite3.Row  → hace que cada fila devuelta sea accesible
      tanto por índice numérico como por nombre de columna (row["term"]).

    La conexión se usa con el context manager `with` en operations.py,
    lo que garantiza commit automático al salir del bloque sin errores
    y rollback si ocurre una excepción.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Crea las tablas de la base de datos si aún no existen.

    Segura para llamarse varias veces (idempotente) gracias al uso de
    CREATE TABLE IF NOT EXISTS.  Debe invocarse una vez al arrancar la
    aplicación antes de cualquier operación de lectura o escritura.

    Tablas creadas
    --------------
    users
        Cuentas de usuario.  password_hash almacena el hash bcrypt.

    concepts
        Almacena los conceptos de aprendizaje.
        - UNIQUE(term, user_id): cada usuario tiene su propio espacio de
          términos; distintos usuarios pueden aprender el mismo concepto
          sin conflicto.
        - user_id identifica al propietario y todas las queries filtran por él.
        - mastery_level tiene un CHECK que garantiza valores entre 0 y 5.

    connections
        Almacena los vínculos entre pares de conceptos.
        - concept_id_a y concept_id_b son FK a concepts(id).
        - ON DELETE CASCADE: si se borra un concepto, sus conexiones desaparecen.

    daily_summaries
        Almacena un resumen de actividad por fecha.
        - (date, user_id) es UNIQUE: un resumen por usuario por día.
    """
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

    # Las migraciones ALTER TABLE deben ejecutarse ANTES de crear los índices
    # que referencian user_id.  En BDs existentes (sprints anteriores) la columna
    # user_id aún no existe; crearla aquí garantiza que los CREATE INDEX
    # del bloque siguiente siempre encuentren la columna.
    _run_migrations()


def _run_migrations() -> None:
    """
    Aplica migraciones de esquema incrementales de forma idempotente.

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
                pass  # columna ya existe — migración idempotente

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
        # Cuando se migra una BD existente, las filas antiguas reciben user_id
        # del DEFAULT definido en el ALTER TABLE.  Si ese DEFAULT fue 1 (versiones
        # anteriores de este script) y aún no existe ningún usuario con id=1 en
        # la tabla users, esa data es legacy sin propietario.  Se mueve a
        # user_id=0 (reservado — nunca asignado por AUTOINCREMENT) para que el
        # primer usuario real que se registre (id=1) no la vea.
        #
        # Condición de seguridad: si ya existe un usuario con id=1, esa data le
        # pertenece legítimamente y no se toca.
        owner_exists = conn.execute(
            "SELECT 1 FROM users WHERE id = 1"
        ).fetchone()
        if owner_exists is None:
            conn.execute("UPDATE concepts        SET user_id = 0 WHERE user_id = 1")
            conn.execute("UPDATE connections     SET user_id = 0 WHERE user_id = 1")
            conn.execute("UPDATE daily_summaries SET user_id = 0 WHERE user_id = 1")

        conn.commit()

        # ── Sprint 11b: UNIQUE(date) → UNIQUE(date, user_id) en daily_summaries ─
        # SQLite no permite ALTER TABLE para cambiar constraints existentes.
        # Usamos el índice con nombre 'uq_daily_date_user' como marcador de
        # migración: si no existe, la tabla aún tiene el constraint antiguo
        # UNIQUE(date) (solo por fecha) y debemos recrearla con el nuevo
        # constraint UNIQUE(date, user_id) para que cada usuario tenga su propio
        # resumen diario sin colisionar con los demás.
        needs_unique_migration = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='index' AND name='uq_daily_date_user'"
        ).fetchone() is None

        if needs_unique_migration:
            # executescript() hace COMMIT implícito al inicio, cerrando la
            # transacción anterior.  Los cambios ya committeados son seguros.
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
            # Recrear índices perdidos al DROP TABLE (DROP elimina todos sus índices).
            # uq_daily_date_user actúa también como marcador de migración aplicada.
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
        # SQLite no permite ALTER TABLE para cambiar constraints existentes.
        # Usamos el índice con nombre 'uq_concepts_term_user' como marcador:
        # si no existe, la tabla tiene el constraint antiguo UNIQUE(term)
        # (global entre todos los usuarios) y se debe recrear.
        #
        # La migración usa INSERT OR IGNORE para que si hubiera alguna
        # colisión (caso imposible con el constraint anterior que ya era
        # global) no interrumpa la copia.  Los id originales se preservan
        # para mantener las FK de la tabla connections intactas.
        # Los índices sobre concepts(user_id) se recrean tras el DROP/RENAME.
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
            # Recrear índices eliminados por el DROP TABLE.
            # 'uq_concepts_term_user' actúa también como marcador de migración.
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
