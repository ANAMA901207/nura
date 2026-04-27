"""
db/operations.py
================
Funciones CRUD puras para interactuar con la base de datos de Nura.

Sprint 11: todas las funciones aceptan user_id (default=1 para compatibilidad
con tests anteriores y datos existentes) y filtran por él en todas las queries.
Nuevas funciones de autenticación: create_user, authenticate_user, get_user_by_id.

Convenciones de seguridad
--------------------------
- Todas las queries usan parámetros SQL (?, ?) — nunca f-strings con datos de usuario.
- Las columnas dinámicas en SET clauses provienen de conjuntos "allowed" definidos
  en el código, no del input del usuario.
- Los inputs de usuario se sanean en save_concept() antes de persistir.
- Las contraseñas se almacenan como hash bcrypt; nunca en texto plano.

Convenciones de error
---------------------
- ValueError  → violación de regla de negocio (term duplicado, ID inexistente,
                nivel de dominio fuera de rango, campo inválido en kwargs).
- AuthError   → credenciales incorrectas en authenticate_user.
  El llamador puede capturar estos tipos para mostrar mensajes amigables.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, date
from typing import Any

import bcrypt

from db.models import Concept, Connection, DailySummary, User
from db.schema import get_connection, get_db_mode


# ── placeholder adapter ───────────────────────────────────────────────────────

def _adapt_query(sql: str, params: tuple = ()) -> tuple[str, tuple]:
    """
    Adapta el SQL y los parámetros al motor de base de datos activo.

    SQLite usa '?' como placeholder; PostgreSQL usa '%s'.  La conexión
    retornada por get_connection() aplica esta transformación automáticamente
    en su método execute(), así que el código de operations.py puede seguir
    escribiendo '?' en todas sus queries sin cambios.

    Esta función está disponible para construir queries dinámicas (SET clauses,
    etc.) que necesiten transformar los placeholders explícitamente antes de
    llamar a métodos fuera de execute().

    Devuelve
    --------
    Tupla (sql_adaptado, params) lista para pasar a conn.execute().
    """
    if get_db_mode() == "postgresql":
        return sql.replace("?", "%s"), params
    return sql, params


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime | None:
    """
    Convierte una cadena ISO 8601 a datetime, o devuelve None si el valor es None.

    SQLite almacena las fechas como texto; esta función centraliza la conversión
    para los campos nullable como last_reviewed.
    """
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _row_to_concept(row: Any) -> Concept:
    """
    Convierte una fila de la tabla concepts en un dataclass Concept.

    Mapea cada columna por nombre (gracias a row_factory = sqlite3.Row)
    y aplica las conversiones de tipo necesarias: texto ISO → datetime,
    entero 0/1 → bool para is_classified.  Los campos añadidos en sprints
    posteriores se leen con comprobación de clave para mantener compatibilidad
    hacia atrás en tests con BDs antiguas.
    """
    keys = row.keys() if hasattr(row, "keys") else []
    return Concept(
        id=row["id"],
        term=row["term"],
        category=row["category"],
        subcategory=row["subcategory"],
        explanation=row["explanation"],
        examples=row["examples"],
        analogy=row["analogy"],
        context=row["context"],
        flashcard_front=row["flashcard_front"],
        flashcard_back=row["flashcard_back"],
        mastery_level=row["mastery_level"],
        created_at=datetime.fromisoformat(row["created_at"]),
        last_reviewed=_parse_dt(row["last_reviewed"]),
        # Sprint 5 fields
        is_classified=bool(row["is_classified"]) if "is_classified" in keys else False,
        user_context=row["user_context"] if "user_context" in keys else "",
        # Sprint 7 fields
        consecutive_correct=row["consecutive_correct"] if "consecutive_correct" in keys else 0,
        consecutive_incorrect=row["consecutive_incorrect"] if "consecutive_incorrect" in keys else 0,
        total_reviews=row["total_reviews"] if "total_reviews" in keys else 0,
        next_review=_parse_dt(row["next_review"]) if "next_review" in keys else None,
        # Sprint 8 SM-2 fields
        sm2_interval=float(row["sm2_interval"]) if "sm2_interval" in keys else 1.0,
        sm2_ef=float(row["sm2_ef"]) if "sm2_ef" in keys else 2.5,
        # Sprint 11 multi-user
        user_id=int(row["user_id"]) if "user_id" in keys else 1,
    )


def _row_to_connection(row: Any) -> Connection:
    """
    Convierte una fila de la tabla connections en un dataclass Connection.
    Sprint 11: lee el campo user_id con fallback a 1 para BDs antiguas.
    """
    keys = row.keys() if hasattr(row, "keys") else []
    return Connection(
        id=row["id"],
        concept_id_a=row["concept_id_a"],
        concept_id_b=row["concept_id_b"],
        relationship=row["relationship"],
        created_at=datetime.fromisoformat(row["created_at"]),
        user_id=int(row["user_id"]) if "user_id" in keys else 1,
    )


def _row_to_daily_summary(row: Any) -> DailySummary:
    """
    Convierte una fila de la tabla daily_summaries en un dataclass DailySummary.

    La columna date se guarda como texto ISO ("2026-04-10") y se convierte
    al tipo date nativo de Python.
    Sprint 11: lee user_id con fallback a 1.
    """
    keys = row.keys() if hasattr(row, "keys") else []
    return DailySummary(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        concepts_captured=row["concepts_captured"],
        new_connections=row["new_connections"],
        concepts_reviewed=row["concepts_reviewed"],
        user_id=int(row["user_id"]) if "user_id" in keys else 1,
    )


def _row_to_user(row: Any) -> User:
    """
    Convierte una fila de la tabla users en un dataclass User.

    Lee los campos de perfil de onboarding (Sprint 15) y la meta diaria
    (Sprint 24) con comprobación de clave para compatibilidad con BDs
    anteriores a cada migración.
    """
    keys = row.keys()
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        created_at=datetime.fromisoformat(row["created_at"]),
        profession=row["profession"]    if "profession"    in keys else "",
        learning_area=row["learning_area"] if "learning_area" in keys else "",
        tech_level=row["tech_level"]    if "tech_level"    in keys else "",
        daily_goal=int(row["daily_goal"]) if "daily_goal" in keys else 3,
        telegram_id=row["telegram_id"]           if "telegram_id"      in keys else None,
        link_code=row["link_code"]               if "link_code"        in keys else None,
        link_code_expiry=row["link_code_expiry"] if "link_code_expiry" in keys else None,
        reminder_time=row["reminder_time"]       if "reminder_time"    in keys else "20:00",
    )


def _concept_exists(conn: Any, concept_id: int) -> bool:
    """
    Comprueba si existe un concepto con el ID dado dentro de una conexión abierta.

    Recibe la conexión como argumento en lugar de abrir una nueva para poder
    ejecutarse dentro de la misma transacción que la operación que la llama.
    Devuelve True si el concepto existe, False en caso contrario.
    """
    row = conn.execute(
        "SELECT 1 FROM concepts WHERE id = ?", (concept_id,)
    ).fetchone()
    return row is not None


def _sanitize_text(text: str, max_len: int) -> str:
    """
    Elimina caracteres de control y limita la longitud del texto.

    Los caracteres de control (U+0000–U+001F salvo \\t y \\n) pueden
    causar problemas en SQL y en la UI.  Se eliminan con una expresión
    regular antes de persistir.

    Parámetros
    ----------
    text    : Texto a sanear.
    max_len : Longitud máxima en caracteres.

    Devuelve
    --------
    str saneado y truncado.
    """
    # Eliminar caracteres de control (excluye \\t y \\n que son legítimos)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return cleaned[:max_len]


# ── auth ──────────────────────────────────────────────────────────────────────

def create_user(username: str, password: str) -> User:
    """
    Crea una cuenta de usuario nueva con contraseña hasheada con bcrypt.

    El hash se genera con bcrypt.hashpw() usando un salt aleatorio de
    coste 12 (balance entre seguridad y velocidad).  La contraseña en
    texto plano NUNCA se almacena ni se registra.

    Parámetros
    ----------
    username : Nombre de usuario (debe ser único).  Se recorta a 64 chars
               y se eliminan espacios iniciales/finales.
    password : Contraseña en texto plano.  Mínimo 1 carácter; el llamador
               debe validar longitud mínima antes de llamar a esta función.

    Devuelve
    --------
    User recién creado con id asignado por SQLite.

    Lanza
    -----
    ValueError : Si el username ya existe o si username/password están vacíos.
    """
    username = username.strip()[:64]
    if not username:
        raise ValueError("El nombre de usuario no puede estar vacío.")
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    # bcrypt.hashpw espera bytes; encode() convierte str → bytes UTF-8
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    now = datetime.now().isoformat()

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash.decode("utf-8"), now),
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"El usuario '{username}' ya existe.")

        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _row_to_user(row)


def authenticate_user(username: str, password: str) -> "User | None":
    """
    Verifica las credenciales de un usuario y devuelve su objeto User.

    Usa bcrypt.checkpw() para comparar la contraseña enviada contra el hash
    almacenado, sin exponer el hash al llamador.  El proceso es O(tiempo de hash)
    independientemente de si el usuario existe, para dificultar enumeración.

    Parámetros
    ----------
    username : Nombre de usuario a autenticar.
    password : Contraseña en texto plano enviada por el usuario.

    Devuelve
    --------
    User si las credenciales son correctas, None si son incorrectas o no existe.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()

    if row is None:
        # Hash ficticio para evitar timing attacks por enumeración de usuarios
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        return None

    user = _row_to_user(row)
    if bcrypt.checkpw(password.encode("utf-8"), user.password_hash.encode("utf-8")):
        return user
    return None


def get_user_by_id(user_id: int) -> "User | None":
    """
    Devuelve el User correspondiente al ID dado, o None si no existe.

    Parámetros
    ----------
    user_id : ID primario del usuario a recuperar.

    Devuelve
    --------
    User si existe, None en caso contrario.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def update_user_profile(
    user_id: int,
    profession: str,
    learning_area: str,
    tech_level: str,
) -> User:
    """
    Actualiza los campos del perfil de onboarding para un usuario existente.

    Sprint 15: persiste la profesión, el área de aprendizaje y el nivel
    técnico que el usuario elige durante el onboarding (o cuando edita su
    perfil desde el sidebar).

    Parámetros
    ----------
    user_id       : ID del usuario a actualizar.
    profession    : Perfil profesional (p. ej. "Analista de crédito/banca").
    learning_area : Área de interés (p. ej. "Finanzas y negocios").
    tech_level    : Nivel de experiencia (p. ej. "Intermedio").

    Devuelve
    --------
    User actualizado con los nuevos valores de perfil.

    Lanza
    -----
    ValueError : Si no existe ningún usuario con ese ID.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No existe ningún usuario con id={user_id}.")
        conn.execute(
            "UPDATE users SET profession = ?, learning_area = ?, tech_level = ? "
            "WHERE id = ?",
            (profession, learning_area, tech_level, user_id),
        )
        updated_row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return _row_to_user(updated_row)


def needs_onboarding(user: "User") -> bool:
    """
    Determina si el usuario todavía necesita completar el onboarding.

    Sprint 15: el onboarding se considera incompleto si cualquiera de los tres
    campos del perfil (profession, learning_area, tech_level) está vacío.  Esto
    cubre tanto cuentas recién registradas como cuentas antiguas migradas desde
    versiones anteriores de Nura.

    Parámetros
    ----------
    user : Objeto User cargado desde la BD.

    Devuelve
    --------
    True si falta al menos un campo del perfil, False si los tres están rellenos.
    """
    return not (
        getattr(user, "profession",    "").strip()
        and getattr(user, "learning_area", "").strip()
        and getattr(user, "tech_level",    "").strip()
    )


# ── concepts ─────────────────────────────────────────────────────────────────

def save_concept(
    term: str,
    context: str = "",
    user_context: str = "",
    user_id: int = 1,
) -> Concept:
    """
    Guarda un concepto nuevo en la base de datos y lo devuelve como Concept.

    Sprint 11
    ---------
    - Acepta user_id para asociar el concepto al usuario correcto.
    - Sanitiza term (límite 500 chars) y context (límite 2000 chars)
      eliminando caracteres de control antes de persistir.

    Comportamiento ante duplicados (Sprint 5 / actualizado en fix post-Sprint 15)
    -------------------------------------------------------------------------------
    La BD usa UNIQUE(term, user_id), así que distintos usuarios pueden tener el
    mismo término sin conflicto.

    Si el término ya existe para ESE usuario con is_classified=False,
    se devuelve el concepto existente para reclasificar.
    Si el término ya existe para ESE usuario con is_classified=True,
    se lanza ValueError.
    Si el término existe para OTRO usuario, no hay conflicto de BD y se
    inserta normalmente como concepto nuevo para este usuario.

    Parámetros
    ----------
    term         : Nombre del concepto (único por usuario en la BD).
    context      : Fuente donde apareció el término (opcional).
    user_context : Contexto adicional ingresado por el usuario (opcional).
    user_id      : ID del usuario propietario del concepto (default=1).

    Devuelve
    --------
    Concept con todos sus campos tal como quedaron en la BD.

    Lanza
    -----
    ValueError : Si ya existe un concepto con el mismo term para este usuario
                 y está clasificado, o si el term viola constraints de la BD.
    """
    # Sanitizar inputs antes de persistir
    term = _sanitize_text(term.strip(), 500)
    context = _sanitize_text(context, 2000)
    user_context = _sanitize_text(user_context, 2000)

    if not term:
        raise ValueError("El término no puede estar vacío.")

    now = datetime.now().isoformat()
    with get_connection() as conn:
        # Verificar si el término ya existe para ESTE usuario
        existing_row = conn.execute(
            "SELECT * FROM concepts WHERE term = ? AND user_id = ?",
            (term, user_id),
        ).fetchone()

        if existing_row is not None:
            existing = _row_to_concept(existing_row)
            if not existing.is_classified:
                return existing  # sin clasificar → devolver para reclasificar
            raise ValueError(f"Concept with term '{term}' already exists.")

        try:
            cursor = conn.execute(
                """
                INSERT INTO concepts (term, context, user_context, created_at, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (term, context, user_context, now, user_id),
            )
        except sqlite3.IntegrityError:
            # Con UNIQUE(term, user_id) esto solo ocurre si hay una condición
            # de carrera donde la misma sesión insertó el mismo término
            # concurrentemente; el pre-check de arriba lo debería haber
            # capturado primero en condiciones normales.
            raise ValueError(
                f"El término '{term}' ya existe para este usuario."
            )

        concept_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return _row_to_concept(row)


def get_concept_by_term(term: str, user_id: int = 1) -> "Concept | None":
    """
    Recupera un concepto por su término exacto para un usuario dado, o None.

    Parámetros
    ----------
    term    : Término a buscar (búsqueda exacta, sensible a mayúsculas).
    user_id : ID del usuario propietario (default=1).

    Devuelve
    --------
    Concept si existe un registro con ese term para ese user_id, None si no.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM concepts WHERE term = ? AND user_id = ?",
            (term, user_id),
        ).fetchone()
        return _row_to_concept(row) if row is not None else None


def get_all_concepts(user_id: int = 1) -> list[Concept]:
    """
    Devuelve todos los conceptos de un usuario, ordenados por ID de creación.

    Parámetros
    ----------
    user_id : ID del usuario cuyos conceptos se quieren recuperar (default=1).

    Devuelve
    --------
    Lista de Concept del usuario, vacía si no tiene conceptos.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM concepts WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [_row_to_concept(r) for r in rows]


def get_concept_by_id(concept_id: int, user_id: int = 1) -> Concept:
    """
    Recupera un concepto por su ID primario, verificando que pertenezca al usuario.

    Parámetros
    ----------
    concept_id : ID del concepto a recuperar.
    user_id    : ID del usuario propietario (default=1).

    Devuelve
    --------
    Concept correspondiente al ID dado.

    Lanza
    -----
    ValueError : Si no existe ningún concepto con ese ID para ese usuario.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ? AND user_id = ?",
            (concept_id, user_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"Concept with id {concept_id} not found.")
        return _row_to_concept(row)


def get_unclassified_concepts(user_id: int = 1) -> list[Concept]:
    """
    Devuelve todos los conceptos de un usuario cuya clasificación no se completó.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    Lista de Concept con is_classified=False para ese usuario, ordenada por ID.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM concepts WHERE is_classified = 0 AND user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [_row_to_concept(r) for r in rows]


def update_concept_classification(
    concept_id: int,
    classification_data: dict,
    user_id: int = 1,
) -> Concept:
    """
    Persiste los datos de clasificación en un concepto y marca is_classified=True.

    Campos reconocidos en classification_data
    ------------------------------------------
    category, subcategory, explanation, examples, analogy,
    flashcard_front, flashcard_back.

    Parámetros
    ----------
    concept_id          : ID del concepto a actualizar.
    classification_data : dict con los campos de clasificación.
    user_id             : ID del propietario — se verifica antes de actualizar (default=1).

    Devuelve
    --------
    Concept con todos los campos actualizados y is_classified=True.

    Lanza
    -----
    ValueError : Si el concept_id no existe para ese usuario.
    """
    allowed_fields = {
        "category", "subcategory", "explanation", "examples",
        "analogy", "flashcard_front", "flashcard_back",
    }
    fields = {k: v for k, v in classification_data.items() if k in allowed_fields}
    fields["is_classified"] = 1

    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM concepts WHERE id = ? AND user_id = ?",
            (concept_id, user_id),
        ).fetchone()
        if row is None:
            raise ValueError(f"Concept with id {concept_id} does not exist.")

        set_clause = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [concept_id, user_id]
        conn.execute(
            f"UPDATE concepts SET {set_clause} WHERE id = ? AND user_id = ?",
            values,
        )
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return _row_to_concept(row)


# ── connections ───────────────────────────────────────────────────────────────

def save_connection(
    concept_id_a: int,
    concept_id_b: int,
    relationship: str = "",
    user_id: int = 1,
) -> Connection:
    """
    Crea un vínculo semántico entre dos conceptos existentes.

    Parámetros
    ----------
    concept_id_a : ID del concepto origen.
    concept_id_b : ID del concepto destino.
    relationship : Descripción del vínculo.
    user_id      : ID del propietario de la conexión (default=1).

    Devuelve
    --------
    Connection recién creada con su ID asignado.

    Lanza
    -----
    ValueError : Si alguno de los dos IDs no corresponde a un concepto existente.
    """
    now = datetime.now().isoformat()
    with get_connection() as conn:
        if not _concept_exists(conn, concept_id_a):
            raise ValueError(f"Concept with id {concept_id_a} does not exist.")
        if not _concept_exists(conn, concept_id_b):
            raise ValueError(f"Concept with id {concept_id_b} does not exist.")

        cursor = conn.execute(
            """
            INSERT INTO connections (concept_id_a, concept_id_b, relationship, created_at, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (concept_id_a, concept_id_b, relationship, now, user_id),
        )
        connection_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM connections WHERE id = ?", (connection_id,)
        ).fetchone()
        return _row_to_connection(row)


def get_connections_for_concept(concept_id: int, user_id: int = 1) -> list[Connection]:
    """
    Devuelve todas las conexiones del usuario en las que participa un concepto.

    Parámetros
    ----------
    concept_id : ID del concepto cuyas conexiones se quieren recuperar.
    user_id    : ID del propietario (default=1).

    Devuelve
    --------
    Lista de Connection ordenada por ID.  Lista vacía si no tiene conexiones.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM connections
            WHERE (concept_id_a = ? OR concept_id_b = ?)
              AND user_id = ?
            ORDER BY id
            """,
            (concept_id, concept_id, user_id),
        ).fetchall()
        return [_row_to_connection(r) for r in rows]


def get_concept_connections_detail(concept_id: int, user_id: int = 1) -> list[dict]:
    """
    Devuelve las conexiones de un concepto como lista de dicts legibles.

    Parámetros
    ----------
    concept_id : ID del concepto cuyos vínculos se quieren detallar.
    user_id    : ID del propietario (default=1).

    Devuelve
    --------
    Lista de dicts con 'concept' (Concept del otro extremo) y 'relationship' (str).
    """
    connections = get_connections_for_concept(concept_id, user_id=user_id)
    result: list[dict] = []
    for conn in connections:
        other_id = (
            conn.concept_id_b if conn.concept_id_a == concept_id
            else conn.concept_id_a
        )
        try:
            other_concept = get_concept_by_id(other_id, user_id=user_id)
            result.append({
                "concept":      other_concept,
                "relationship": conn.relationship,
            })
        except ValueError:
            pass
    return result


def get_all_connections(user_id: int = 1) -> list[Connection]:
    """
    Devuelve todas las conexiones de un usuario, ordenadas por ID.

    Parámetros
    ----------
    user_id : ID del propietario (default=1).
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM connections WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [_row_to_connection(r) for r in rows]


# ── mastery ───────────────────────────────────────────────────────────────────

def update_mastery_level(concept_id: int, level: int, user_id: int = 1) -> Concept:
    """
    Actualiza el nivel de dominio de un concepto y devuelve el concepto actualizado.

    Parámetros
    ----------
    concept_id : ID del concepto a actualizar.
    level      : Nuevo nivel de dominio (0-5).
    user_id    : ID del propietario (default=1).

    Lanza
    -----
    ValueError : Si level está fuera del rango 0-5 o si el concept_id no existe.
    """
    if not (0 <= level <= 5):
        raise ValueError(f"mastery_level must be between 0 and 5, got {level}.")
    with get_connection() as conn:
        if not _concept_exists(conn, concept_id):
            raise ValueError(f"Concept with id {concept_id} does not exist.")
        conn.execute(
            "UPDATE concepts SET mastery_level = ? WHERE id = ? AND user_id = ?",
            (level, concept_id, user_id),
        )
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return _row_to_concept(row)


def record_flashcard_result(
    concept_id: int,
    correct: bool,
    user_id: int = 1,
) -> Concept:
    """
    Registra el resultado de una revisión de flashcard e implementa el algoritmo SM-2.

    SM-2 (SuperMemo 2): calcula cuándo debe volverse a revisar cada concepto
    para maximizar la retención a largo plazo.

    Reglas cuando correct=True (q=4):
        nuevo_ef = ef + 0.0  (q=4 no cambia EF)
        nuevo_ef = max(1.3, nuevo_ef)
        Si consecutive_correct == 1 → intervalo = 1
        Si consecutive_correct == 2 → intervalo = 6
        Si >= 3 → intervalo = round(intervalo_anterior * ef)
        next_review = hoy + intervalo días

    Reglas cuando correct=False:
        nuevo_ef = max(1.3, ef - 0.2)
        intervalo = 1
        next_review = hoy + 1 día

    Parámetros
    ----------
    concept_id : ID del concepto cuya flashcard se revisó.
    correct    : True si "✅ Lo sabía", False si "❌ No lo sabía".
    user_id    : ID del propietario (default=1).

    Devuelve
    --------
    Concept con todos los campos actualizados.

    Lanza
    -----
    ValueError : Si el concept_id no existe.
    """
    from datetime import timedelta

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Concept with id {concept_id} does not exist.")

        concept = _row_to_concept(row)
        now = datetime.now()

        ef = concept.sm2_ef
        interval = concept.sm2_interval

        if correct:
            new_consec_correct = concept.consecutive_correct + 1
            new_consec_incorrect = 0

            new_ef = ef + (0.1 - (5 - 4) * (0.08 + (5 - 4) * 0.02))
            new_ef = max(1.3, new_ef)

            if new_consec_correct == 1:
                new_interval = 1.0
            elif new_consec_correct == 2:
                new_interval = 6.0
            else:
                new_interval = round(interval * ef)
                new_interval = max(1.0, float(new_interval))

            new_mastery = concept.mastery_level
            if new_consec_correct >= 5:
                new_mastery = max(new_mastery, 4)
            elif new_consec_correct >= 3:
                new_mastery = max(new_mastery, 3)
            elif new_consec_correct >= 1:
                new_mastery = max(new_mastery, 2)
            new_mastery = min(new_mastery, 5)

        else:
            new_consec_correct = 0
            new_consec_incorrect = concept.consecutive_incorrect + 1

            new_ef = max(1.3, ef - 0.2)
            new_interval = 1.0

            new_mastery = concept.mastery_level
            if new_consec_incorrect >= 3:
                new_mastery = max(0, new_mastery - 1)

        new_total_reviews = concept.total_reviews + 1
        next_review = now + timedelta(days=new_interval)

        conn.execute(
            """
            UPDATE concepts SET
                consecutive_correct   = ?,
                consecutive_incorrect = ?,
                total_reviews         = ?,
                mastery_level         = ?,
                last_reviewed         = ?,
                next_review           = ?,
                sm2_ef                = ?,
                sm2_interval          = ?
            WHERE id = ?
            """,
            (
                new_consec_correct,
                new_consec_incorrect,
                new_total_reviews,
                new_mastery,
                now.isoformat(),
                next_review.isoformat(),
                new_ef,
                new_interval,
                concept_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return _row_to_concept(row)


def get_concepts_due_today(user_id: int = 1) -> list[Concept]:
    """
    Devuelve los conceptos clasificados del usuario cuyo next_review es hoy o anterior.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    list[Concept] — puede ser vacía si no hay conceptos pendientes hoy.
    """
    today_str = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM concepts
            WHERE is_classified = 1
              AND next_review IS NOT NULL
              AND SUBSTR(next_review, 1, 10) <= ?
              AND user_id = ?
            ORDER BY next_review ASC
            """,
            (today_str, user_id),
        ).fetchall()
    return [_row_to_concept(r) for r in rows]


def update_concept_fields(concept_id: int, user_id: int = 1, **kwargs: Any) -> Concept:
    """
    Actualiza campos textuales de un concepto existente y devuelve el concepto completo.

    Campos actualizables
    --------------------
    category, subcategory, explanation, examples, analogy,
    context, flashcard_front, flashcard_back, last_reviewed, is_classified, user_context.

    Parámetros
    ----------
    concept_id : ID del concepto a actualizar.
    user_id    : ID del propietario (default=1).
    **kwargs   : Pares campo=valor con los nuevos contenidos.

    Lanza
    -----
    ValueError : Si se pasa algún nombre de campo no permitido o concept_id no existe.
    """
    allowed = {
        "term",
        "category", "subcategory", "explanation", "examples",
        "analogy", "context", "flashcard_front", "flashcard_back",
        "last_reviewed", "is_classified", "user_context",
    }
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Campos no permitidos en update_concept_fields: {invalid}")

    if not kwargs:
        return get_concept_by_id(concept_id, user_id=user_id)

    with get_connection() as conn:
        if not _concept_exists(conn, concept_id):
            raise ValueError(f"Concept with id {concept_id} does not exist.")

        set_clause = ", ".join(f"{key} = ?" for key in kwargs)
        values = list(kwargs.values()) + [concept_id, user_id]
        conn.execute(
            f"UPDATE concepts SET {set_clause} WHERE id = ? AND user_id = ?",
            values,
        )
        row = conn.execute(
            "SELECT * FROM concepts WHERE id = ?", (concept_id,)
        ).fetchone()
        return _row_to_concept(row)


# ── delete concept ────────────────────────────────────────────────────────────

def delete_concept(concept_id: int, user_id: int = 1) -> bool:
    """
    Elimina un concepto y todas sus conexiones de la base de datos.

    Borra primero las filas de la tabla `connections` en las que el concepto
    aparezca como extremo A o extremo B (cascada manual), y luego borra el
    propio concepto de la tabla `concepts`.

    Parámetros
    ----------
    concept_id : ID del concepto a eliminar.
    user_id    : ID del propietario; la operación solo procede si el concepto
                 pertenece a este usuario.

    Devuelve
    --------
    True  si el concepto existía y fue eliminado.
    False si no se encontró ningún concepto con ese ID y user_id.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM concepts WHERE id = ? AND user_id = ?",
            (concept_id, user_id),
        ).fetchone()
        if not row:
            return False

        # Eliminar conexiones en cascada antes de borrar el concepto
        conn.execute(
            "DELETE FROM connections WHERE concept_id_a = ? OR concept_id_b = ?",
            (concept_id, concept_id),
        )
        conn.execute(
            "DELETE FROM concepts WHERE id = ? AND user_id = ?",
            (concept_id, user_id),
        )
        return True


# ── daily summary ─────────────────────────────────────────────────────────────

def get_or_create_daily_summary(summary_date: date, user_id: int = 1) -> DailySummary:
    """
    Devuelve el resumen del día dado para un usuario, creándolo con contadores
    en cero si no existe.

    Parámetros
    ----------
    summary_date : Fecha del resumen a recuperar o crear.
    user_id      : ID del usuario (default=1).

    Devuelve
    --------
    DailySummary existente o recién creado para esa fecha y usuario.
    """
    date_str = summary_date.isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM daily_summaries WHERE date = ? AND user_id = ?",
            (date_str, user_id),
        ).fetchone()
        if row is not None:
            return _row_to_daily_summary(row)

        cursor = conn.execute(
            """
            INSERT INTO daily_summaries (date, concepts_captured, new_connections, concepts_reviewed, user_id)
            VALUES (?, 0, 0, 0, ?)
            """,
            (date_str, user_id),
        )
        row = conn.execute(
            "SELECT * FROM daily_summaries WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _row_to_daily_summary(row)


def update_daily_summary(
    summary_date: date,
    user_id: int = 1,
    **kwargs: Any,
) -> DailySummary:
    """
    Actualiza uno o varios contadores del resumen diario de un usuario.

    Parámetros
    ----------
    summary_date : Fecha del resumen a actualizar.
    user_id      : ID del usuario (default=1).
    **kwargs     : Pares campo=valor con los nuevos valores de los contadores.
                   Campos aceptados: concepts_captured, new_connections, concepts_reviewed.

    Lanza
    -----
    ValueError : Si se pasa algún nombre de campo no reconocido.
    """
    allowed = {"concepts_captured", "new_connections", "concepts_reviewed"}
    invalid = set(kwargs) - allowed
    if invalid:
        raise ValueError(f"Invalid fields for DailySummary update: {invalid}")

    summary = get_or_create_daily_summary(summary_date, user_id=user_id)
    date_str = summary_date.isoformat()

    if not kwargs:
        return summary

    set_clause = ", ".join(f"{key} = ?" for key in kwargs)
    values = list(kwargs.values()) + [date_str, user_id]

    with get_connection() as conn:
        conn.execute(
            f"UPDATE daily_summaries SET {set_clause} WHERE date = ? AND user_id = ?",
            values,
        )
        row = conn.execute(
            "SELECT * FROM daily_summaries WHERE date = ? AND user_id = ?",
            (date_str, user_id),
        ).fetchone()
        return _row_to_daily_summary(row)


# ── analytics ─────────────────────────────────────────────────────────────────

def get_mastery_by_category(user_id: int = 1) -> dict[str, float]:
    """
    Calcula el promedio de mastery_level agrupado por categoria para un usuario.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    dict[str, float] con {categoria: promedio_mastery}.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT category, AVG(mastery_level) AS avg_mastery
            FROM concepts
            WHERE is_classified = 1
              AND category IS NOT NULL
              AND category != ''
              AND user_id = ?
            GROUP BY category
            ORDER BY category
            """,
            (user_id,),
        ).fetchall()
    return {row["category"]: round(float(row["avg_mastery"]), 2) for row in rows}


def get_streak(user_id: int = 1) -> int:
    """
    Cuenta los días consecutivos hacia atrás desde hoy en que el usuario
    capturó al menos 1 concepto nuevo.

    Sprint 24: usa la fecha de `created_at` de la tabla `concepts` en lugar
    de `daily_summaries`, lo que garantiza que el streak refleja capturas
    reales independientemente del estado de los resúmenes diarios.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    int — días consecutivos con al menos 1 concepto capturado.
          0 si hoy no se capturó ningún concepto.
    """
    from datetime import timedelta

    today = date.today()
    streak = 0
    check_date = today

    with get_connection() as conn:
        for _ in range(730):
            date_str = check_date.isoformat()
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM concepts
                WHERE user_id = ?
                  AND SUBSTR(created_at, 1, 10) = ?
                """,
                (user_id, date_str),
            ).fetchone()
            if row and row["cnt"] > 0:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

    return streak


def get_today_count(user_id: int = 1) -> int:
    """
    Cuenta los conceptos capturados hoy (fecha local) por el usuario.

    Sprint 24: consulta directamente la tabla `concepts` usando
    la fecha local de `created_at` para calcular el progreso del día.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    int — número de conceptos cuyo `created_at` tiene la fecha de hoy.
    """
    today_str = date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM concepts
            WHERE user_id = ?
              AND SUBSTR(created_at, 1, 10) = ?
            """,
            (user_id, today_str),
        ).fetchone()
    return row["cnt"] if row else 0


def get_daily_goal(user_id: int = 1) -> int:
    """
    Retorna la meta diaria de conceptos del usuario.

    Sprint 24: lee el campo `daily_goal` de la tabla `users`.
    Si el usuario no existe o el campo no está presente (BD antigua),
    devuelve 3 como valor por defecto.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    int — meta diaria configurada por el usuario (mínimo 1, default 3).
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT daily_goal FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return 3
    keys = row.keys() if hasattr(row, "keys") else []
    return int(row["daily_goal"]) if "daily_goal" in keys else 3


def update_daily_goal(user_id: int, goal: int) -> None:
    """
    Actualiza la meta diaria de conceptos del usuario en la BD.

    Sprint 24: persiste el campo `daily_goal` en la tabla `users`.
    El valor se recorta al rango [1, 50] para evitar metas absurdas.

    Parámetros
    ----------
    user_id : ID del usuario a actualizar.
    goal    : Nueva meta diaria (se ajusta al rango [1, 50]).

    Lanza
    -----
    ValueError : Si no existe ningún usuario con ese ID.
    """
    goal = max(1, min(50, int(goal)))
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No existe ningún usuario con id={user_id}.")
        conn.execute(
            "UPDATE users SET daily_goal = ? WHERE id = ?",
            (goal, user_id),
        )


def clear_legacy_data() -> dict[str, int]:
    """
    Elimina todos los registros con user_id=0 (data legacy/migrada sin propietario).

    user_id=0 es el valor reservado que _run_migrations() asigna automáticamente
    a las filas que existían antes de la migración multi-usuario del Sprint 11
    y que no tienen ningún usuario real como propietario.

    Esta función es segura de llamar en cualquier momento:
    - Si no hay data legacy, devuelve conteos en cero.
    - Si hay un usuario con id=0 (imposible con AUTOINCREMENT), no elimina nada.

    Uso típico
    ----------
    Llamar desde scripts de mantenimiento o desde la UI de administración cuando
    se quiere limpiar el historial de captura anterior a la migración multi-usuario.

    Devuelve
    --------
    dict con el número de filas eliminadas por tabla:
        {"concepts": int, "connections": int, "daily_summaries": int}
    """
    with get_connection() as conn:
        c_concepts = conn.execute(
            "DELETE FROM concepts WHERE user_id = 0"
        ).rowcount
        c_connections = conn.execute(
            "DELETE FROM connections WHERE user_id = 0"
        ).rowcount
        c_summaries = conn.execute(
            "DELETE FROM daily_summaries WHERE user_id = 0"
        ).rowcount

    return {
        "concepts":        c_concepts,
        "connections":     c_connections,
        "daily_summaries": c_summaries,
    }


# ── Sprint 25: vinculación con Telegram ───────────────────────────────────────

def get_user_by_telegram_id(telegram_id: str) -> "User | None":
    """
    Devuelve el User vinculado al telegram_id dado, o None si no existe.

    Parámetros
    ----------
    telegram_id : ID de Telegram del usuario (como string).

    Devuelve
    --------
    User si hay un registro con ese telegram_id, None en caso contrario.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (str(telegram_id),)
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def set_telegram_id(user_id: int, telegram_id: str) -> None:
    """
    Vincula un telegram_id con el usuario dado.

    Parámetros
    ----------
    user_id     : ID del usuario en Nura.
    telegram_id : ID de Telegram a vincular.

    Lanza
    -----
    ValueError : Si no existe ningún usuario con ese ID.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No existe ningún usuario con id={user_id}.")
        conn.execute(
            "UPDATE users SET telegram_id = ? WHERE id = ?",
            (str(telegram_id), user_id),
        )


def save_link_code(user_id: int, code: str, expiry: str) -> None:
    """
    Guarda el código de vinculación temporal y su fecha de expiración.

    Parámetros
    ----------
    user_id : ID del usuario en Nura.
    code    : Código de 6 dígitos generado.
    expiry  : Timestamp ISO 8601 de expiración (ahora + 10 minutos).

    Lanza
    -----
    ValueError : Si no existe ningún usuario con ese ID.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No existe ningún usuario con id={user_id}.")
        conn.execute(
            "UPDATE users SET link_code = ?, link_code_expiry = ? WHERE id = ?",
            (code, expiry, user_id),
        )


def get_user_by_link_code(code: str) -> "User | None":
    """
    Devuelve el User cuyo link_code coincide con el código dado y no ha expirado.

    Parámetros
    ----------
    code : Código de 6 dígitos enviado por el usuario en Telegram.

    Devuelve
    --------
    User si el código existe y no ha expirado, None en caso contrario
    (código incorrecto, expirado o ya usado).
    """
    now_str = datetime.now().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM users
            WHERE link_code = ?
              AND link_code_expiry IS NOT NULL
              AND link_code_expiry > ?
            """,
            (code, now_str),
        ).fetchone()
    return _row_to_user(row) if row is not None else None


def get_dominated_concepts(user_id: int = 1) -> list[Concept]:
    """
    Devuelve los conceptos del usuario con mastery_level >= 4.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    list[Concept] — puede ser vacía si no hay conceptos con mastery >= 4.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM concepts
            WHERE mastery_level >= 4
              AND user_id = ?
            ORDER BY mastery_level DESC, term ASC
            """,
            (user_id,),
        ).fetchall()
    return [_row_to_concept(r) for r in rows]


# ── Sprint 12: análisis de patrones adaptativos ───────────────────────────────

def get_weak_categories(user_id: int = 1) -> list[dict]:
    """
    Retorna categorías con más de 2 conceptos clasificados y mastery promedio < 2.5.

    Se usan para identificar áreas donde el usuario tiene conocimiento incompleto:
    tiene suficiente exposición (> 2 conceptos) pero bajo dominio (< 2.5/5).
    Los resultados se ordenan de menor a mayor mastery para priorizar las más débiles.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    list[dict] — cada dict tiene: category (str), avg_mastery (float), count (int).
    Lista vacía si ninguna categoría cumple los criterios.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT category,
                   AVG(mastery_level) AS avg_mastery,
                   COUNT(*)           AS cnt
            FROM   concepts
            WHERE  is_classified = 1
              AND  category IS NOT NULL
              AND  category != ''
              AND  user_id = ?
            GROUP  BY category
            HAVING COUNT(*) > 2 AND AVG(mastery_level) < 2.5
            ORDER  BY AVG(mastery_level) ASC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "category":    row["category"],
            "avg_mastery": round(float(row["avg_mastery"]), 2),
            "count":       row["cnt"],
        }
        for row in rows
    ]


def get_neglected_concepts(user_id: int = 1, days: int = 7) -> list[Concept]:
    """
    Retorna conceptos clasificados sin actividad en más de N días.

    Un concepto se considera "descuidado" si:
    - Fue capturado hace más de `days` días, Y
    - Nunca fue revisado (last_reviewed IS NULL), O
    - La última revisión fue hace más de `days` días.

    El requisito de antigüedad evita incluir conceptos recién capturados.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).
    days    : Umbral de inactividad en días (default=7).

    Devuelve
    --------
    list[Concept] ordenada por last_reviewed ascendente (NULLs primero).
    """
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM concepts
            WHERE  is_classified = 1
              AND  user_id       = ?
              AND  created_at    < ?
              AND  (last_reviewed IS NULL OR last_reviewed < ?)
            ORDER  BY last_reviewed ASC
            """,
            (user_id, cutoff, cutoff),
        ).fetchall()
    return [_row_to_concept(r) for r in rows]


def get_struggling_concepts(user_id: int = 1, min_failures: int = 3) -> list[Concept]:
    """
    Retorna conceptos con consecutive_incorrect >= min_failures.

    Identifica los conceptos con los que el usuario sigue fallando en flashcards,
    lo que indica que necesitan más atención o un enfoque de explicación diferente.

    Parámetros
    ----------
    user_id      : ID del usuario (default=1).
    min_failures : Mínimo de fallos consecutivos para incluir el concepto (default=3).

    Devuelve
    --------
    list[Concept] ordenada por consecutive_incorrect descendente (los más difíciles primero).
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM concepts
            WHERE  consecutive_incorrect >= ?
              AND  user_id              = ?
              AND  is_classified        = 1
            ORDER  BY consecutive_incorrect DESC, term ASC
            """,
            (min_failures, user_id),
        ).fetchall()
    return [_row_to_concept(r) for r in rows]


def get_learning_preference(user_id: int = 1) -> str:
    """
    Detecta si el usuario aprende más por flashcards o por conversación con el tutor.

    Heurística: si el total de revisiones en flashcards supera el doble del
    número de conceptos capturados, el usuario prefiere las flashcards para
    repasar.  En caso contrario, prefiere el modo chat/tutor.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    'flashcards' — si total_reviews > total_concepts * 2.
    'chat'       — en cualquier otro caso (base de datos vacía incluida).
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT SUM(total_reviews) AS total_reviews,
                   COUNT(*)           AS total_concepts
            FROM   concepts
            WHERE  user_id       = ?
              AND  is_classified = 1
            """,
            (user_id,),
        ).fetchone()

    if row is None or not row["total_concepts"]:
        return "chat"

    total_reviews = row["total_reviews"] or 0
    total_concepts = row["total_concepts"]

    return "flashcards" if total_reviews > total_concepts * 2 else "chat"


def get_weekly_insight_data(user_id: int = 1) -> dict:
    """
    Recopila métricas de la semana actual para el insight adaptativo.

    Combina datos de múltiples tablas para generar un resumen de aprendizaje
    de los últimos 7 días: conceptos nuevos, área más fuerte, área más débil,
    conceptos dominados y racha activa.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    dict con las claves:
        conceptos_esta_semana (int)   — conceptos capturados en los últimos 7 días.
        categoria_mas_fuerte  (str)   — categoría con mayor mastery promedio ('').
        categoria_mas_debil   (str)   — categoría con menor mastery promedio ('').
        conceptos_dominados   (int)   — conceptos con mastery >= 4.
        racha                 (int)   — días consecutivos de actividad.
    """
    from datetime import timedelta

    week_ago = (datetime.now() - timedelta(days=7)).isoformat()

    with get_connection() as conn:
        row_weekly = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM   concepts
            WHERE  user_id    = ?
              AND  created_at >= ?
            """,
            (user_id, week_ago),
        ).fetchone()
        conceptos_esta_semana = row_weekly["cnt"] if row_weekly else 0

        rows_mastery = conn.execute(
            """
            SELECT category, AVG(mastery_level) AS avg_mastery
            FROM   concepts
            WHERE  is_classified = 1
              AND  category IS NOT NULL
              AND  category != ''
              AND  user_id  = ?
            GROUP  BY category
            """,
            (user_id,),
        ).fetchall()

    mastery_map = {r["category"]: float(r["avg_mastery"]) for r in rows_mastery}
    categoria_mas_fuerte = max(mastery_map, key=mastery_map.__getitem__) if mastery_map else ""
    categoria_mas_debil  = min(mastery_map, key=mastery_map.__getitem__) if mastery_map else ""

    dominated = get_dominated_concepts(user_id=user_id)
    streak    = get_streak(user_id=user_id)

    return {
        "conceptos_esta_semana": conceptos_esta_semana,
        "categoria_mas_fuerte":  categoria_mas_fuerte,
        "categoria_mas_debil":   categoria_mas_debil,
        "conceptos_dominados":   len(dominated),
        "racha":                 streak,
    }


def get_session_stats(user_id: int = 1) -> dict:
    """
    Retorna las estadísticas de la sesión actual del usuario.

    Combina datos del resumen diario con el total histórico de conceptos para
    determinar si es la primera sesión real del usuario.  El campo quiz_score
    no puede inferirse desde la BD y siempre se devuelve como None; el llamador
    debe pasarlo manualmente cuando lo tenga disponible.

    Parámetros
    ----------
    user_id : ID del usuario (default=1).

    Devuelve
    --------
    dict con las claves:
        conceptos_hoy     (int)   — conceptos capturados hoy.
        conexiones_hoy    (int)   — conexiones nuevas hoy.
        repasados_hoy     (int)   — conceptos repasados hoy.
        racha             (int)   — días consecutivos activos.
        es_primera_sesion (bool)  — True si todos los conceptos del usuario
                                    fueron capturados hoy (primera sesión real).
        quiz_score        (None)  — siempre None; debe asignarse externamente.
    """
    today   = date.today()
    summary = get_or_create_daily_summary(today, user_id=user_id)

    conceptos_hoy  = summary.concepts_captured
    conexiones_hoy = summary.new_connections
    repasados_hoy  = summary.concepts_reviewed
    racha          = get_streak(user_id=user_id)

    total_conceptos   = len(get_all_concepts(user_id=user_id))
    es_primera_sesion = (conceptos_hoy > 0) and (total_conceptos <= conceptos_hoy)

    return {
        "conceptos_hoy":     conceptos_hoy,
        "conexiones_hoy":    conexiones_hoy,
        "repasados_hoy":     repasados_hoy,
        "racha":             racha,
        "es_primera_sesion": es_primera_sesion,
        "quiz_score":        None,
    }


# ── Sprint 26: recordatorios automáticos por Telegram ─────────────────────────

import re as _re


def get_reminder_time(user_id: int) -> str:
    """
    Devuelve la hora configurada de recordatorio diario del usuario.

    Parámetros
    ----------
    user_id : ID del usuario en Nura.

    Devuelve
    --------
    str — hora en formato "HH:MM". Retorna "20:00" si el campo no existe.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT reminder_time FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return "20:00"
    val = row[0] if hasattr(row, "__getitem__") and not hasattr(row, "keys") else (
        row["reminder_time"] if "reminder_time" in row.keys() else None
    )
    return val if val else "20:00"


def set_reminder_time(user_id: int, time_str: str) -> None:
    """
    Guarda la hora de recordatorio del usuario después de validar el formato HH:MM.

    Parámetros
    ----------
    user_id  : ID del usuario en Nura.
    time_str : Cadena en formato "HH:MM" (00:00 – 23:59).

    Lanza
    -----
    ValueError : Si time_str no cumple el formato HH:MM o la hora/minuto están
                 fuera de rango.
    """
    if not _re.fullmatch(r"\d{2}:\d{2}", time_str):
        raise ValueError(f"Formato inválido: '{time_str}'. Se esperaba HH:MM.")
    hh, mm = int(time_str[:2]), int(time_str[3:])
    if hh > 23 or mm > 59:
        raise ValueError(
            f"Hora fuera de rango: '{time_str}'. HH 00-23, MM 00-59."
        )
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET reminder_time = ? WHERE id = ?",
            (time_str, user_id),
        )


def get_users_to_remind(current_time_str: str) -> "list[User]":
    """
    Devuelve la lista de usuarios que deben recibir el recordatorio ahora.

    Un usuario se incluye si:
      (a) tiene telegram_id vinculado (no nulo, no vacío),
      (b) su reminder_time coincide con current_time_str,
      (c) el número de conceptos capturados hoy es menor que su daily_goal.

    Parámetros
    ----------
    current_time_str : Hora actual en formato "HH:MM".

    Devuelve
    --------
    list[User] — puede ser vacía.
    """
    today_str = date.today().isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT u.*
            FROM   users u
            WHERE  u.telegram_id IS NOT NULL
              AND  u.telegram_id  != ''
              AND  u.reminder_time = ?
              AND  (
                SELECT COUNT(*)
                FROM   concepts c
                WHERE  c.user_id = u.id
                  AND  SUBSTR(c.created_at, 1, 10) = ?
              ) < u.daily_goal
            """,
            (current_time_str, today_str),
        ).fetchall()
    return [_row_to_user(r) for r in rows]


# ── Sprint 28: árbol jerárquico conceptual ────────────────────────────────────

def save_hierarchy(
    user_id: int,
    child_id: int,
    parent_id: int,
    relation_type: str,
) -> None:
    """
    Guarda una relación jerárquica entre dos conceptos del usuario.

    Parámetros
    ----------
    user_id       : ID del usuario propietario.
    child_id      : ID del concepto hijo (el más específico).
    parent_id     : ID del concepto padre (el más general).
    relation_type : Tipo de relación: "es_tipo_de", "contiene" o "es_parte_de".

    Lanza
    -----
    ValueError : Si algún concepto o usuario no existe.
    """
    with get_connection() as conn:
        for cid in (child_id, parent_id):
            row = conn.execute("SELECT id FROM concepts WHERE id = ?", (cid,)).fetchone()
            if row is None:
                raise ValueError(f"No existe el concepto con id={cid}.")
        created_at = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO concept_hierarchy
                (user_id, child_id, parent_id, relation_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, child_id, parent_id, relation_type, created_at),
        )


def get_hierarchy(user_id: int) -> "list[dict]":
    """
    Devuelve todas las relaciones jerárquicas del usuario.

    Parámetros
    ----------
    user_id : ID del usuario.

    Devuelve
    --------
    list[dict] — cada dict tiene las claves:
        id, user_id, child_id, parent_id, relation_type, created_at,
        child_term, parent_term.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT h.id,
                   h.user_id,
                   h.child_id,
                   h.parent_id,
                   h.relation_type,
                   h.created_at,
                   c.term  AS child_term,
                   p.term  AS parent_term
            FROM   concept_hierarchy h
            JOIN   concepts c ON c.id = h.child_id
            JOIN   concepts p ON p.id = h.parent_id
            WHERE  h.user_id = ?
            ORDER  BY h.created_at
            """,
            (user_id,),
        ).fetchall()
    result = []
    for r in rows:
        keys = r.keys() if hasattr(r, "keys") else []
        result.append({
            "id":            r["id"]            if "id"            in keys else r[0],
            "user_id":       r["user_id"]       if "user_id"       in keys else r[1],
            "child_id":      r["child_id"]      if "child_id"      in keys else r[2],
            "parent_id":     r["parent_id"]     if "parent_id"     in keys else r[3],
            "relation_type": r["relation_type"] if "relation_type" in keys else r[4],
            "created_at":    r["created_at"]    if "created_at"    in keys else r[5],
            "child_term":    r["child_term"]    if "child_term"    in keys else r[6],
            "parent_term":   r["parent_term"]   if "parent_term"   in keys else r[7],
        })
    return result


def get_concept_tree(user_id: int, category: "str | None" = None) -> dict:
    """
    Construye el árbol jerárquico de conceptos del usuario.

    Parámetros
    ----------
    user_id  : ID del usuario.
    category : Si se proporciona, filtra por la categoría del concepto padre.

    Devuelve
    --------
    dict anidado — estructura recursiva:
        {
          "term_padre": {
            "relation": "contiene",
            "children": {
              "term_hijo": {
                "relation": "es_tipo_de",
                "children": { ... }
              }
            }
          }
        }
    Conceptos sin padre (raíces) aparecen en el nivel superior.
    """
    relations = get_hierarchy(user_id)

    # Filtrar por categoría si se especifica
    if category:
        # Cargar términos con su categoría para filtrar
        with get_connection() as conn:
            cat_rows = conn.execute(
                "SELECT id FROM concepts WHERE user_id = ? AND LOWER(category) LIKE LOWER(?)",
                (user_id, f"%{category}%"),
            ).fetchall()
        cat_ids = {r[0] for r in cat_rows}
        relations = [
            r for r in relations
            if r["child_id"] in cat_ids or r["parent_id"] in cat_ids
        ]

    # Índice de hijos por padre
    children_map: dict[int, list[dict]] = {}
    all_child_ids: set[int] = set()
    id_to_term: dict[int, str] = {}

    for rel in relations:
        pid, cid = rel["parent_id"], rel["child_id"]
        id_to_term[pid] = rel["parent_term"]
        id_to_term[cid] = rel["child_term"]
        all_child_ids.add(cid)
        children_map.setdefault(pid, []).append(rel)

    # Raíces: padres que no son hijos de nadie
    root_ids = [pid for pid in children_map if pid not in all_child_ids]

    def _build_node(concept_id: int) -> dict:
        node: dict = {"children": {}}
        for rel in children_map.get(concept_id, []):
            cid = rel["child_id"]
            child_term = id_to_term[cid]
            node["children"][child_term] = {
                "relation": rel["relation_type"],
                **_build_node(cid),
            }
        return node

    tree: dict = {}
    for root_id in root_ids:
        root_term = id_to_term[root_id]
        tree[root_term] = _build_node(root_id)

    return tree
