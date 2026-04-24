"""
tests/test_sprint24.py
======================
Harness para Sprint 24 — Streak y meta diaria.

Verifica:
- get_streak: usuario nuevo → 0, solo hoy → 1, 3 días consecutivos → 3,
              streak roto por gap → días desde gap.
- get_today_count: conteo correcto de conceptos de hoy.
- get_daily_goal: usuario nuevo → 3 (default).
- update_daily_goal: cambio persiste en BD.

Estrategia de fixture
---------------------
Cada test crea una BD SQLite en memoria (usando DB_PATH temporal con NamedTemporaryFile).
init_db() crea el esquema y create_user() registra el usuario de prueba.
Los conceptos se insertan con fechas específicas en created_at para controlar el streak.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import db.schema as _schema
from db.schema import init_db
from db.operations import (
    create_user,
    get_daily_goal,
    get_streak,
    get_today_count,
    update_daily_goal,
)


# ── fixture: BD aislada por test ──────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path):
    """
    Crea una BD SQLite temporal para cada test.

    Sobreescribe db.schema.DB_PATH con la ruta temporal y fuerza el modo
    SQLite (DATABASE_URL="") para que get_connection() apunte a la BD del test.
    Al terminar el test restaura los valores originales.
    """
    db_file = tmp_path / "test_nura.db"
    original_path = _schema.DB_PATH
    original_url  = os.environ.get("DATABASE_URL", "")

    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""

    init_db()

    yield db_file

    _schema.DB_PATH = original_path
    if original_url:
        os.environ["DATABASE_URL"] = original_url
    else:
        os.environ["DATABASE_URL"] = ""


def _insert_concept_on_date(db_path: Path, user_id: int, term: str, day: date) -> None:
    """Inserta un concepto con created_at en la fecha indicada (solo para tests)."""
    created_at = datetime.combine(day, datetime.min.time()).isoformat()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO concepts
              (term, created_at, user_id,
               category, subcategory, explanation, examples,
               analogy, context, flashcard_front, flashcard_back,
               mastery_level)
            VALUES (?, ?, ?, '', '', '', '', '', '', '', '', 0)
            """,
            (term, created_at, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_streak_zero_new_user(tmp_db):
    """
    Usuario sin conceptos → get_streak retorna 0.
    """
    user = create_user("ana", "password123")
    result = get_streak(user.id)
    assert result == 0, f"Usuario sin conceptos debe tener streak 0, obtuvo {result}"


def test_streak_one_day(tmp_db):
    """
    Conceptos solo hoy → get_streak retorna 1.
    """
    user = create_user("ana", "password123")
    _insert_concept_on_date(tmp_db, user.id, "concepto_hoy", date.today())
    result = get_streak(user.id)
    assert result == 1, f"Conceptos solo hoy debe dar streak 1, obtuvo {result}"


def test_streak_consecutive_days(tmp_db):
    """
    Conceptos en 3 fechas consecutivas → get_streak retorna 3.
    """
    user = create_user("ana", "password123")
    today = date.today()
    for delta in range(3):
        _insert_concept_on_date(tmp_db, user.id, f"term_{delta}", today - timedelta(days=delta))

    result = get_streak(user.id)
    assert result == 3, f"3 días consecutivos deben dar streak 3, obtuvo {result}"


def test_streak_broken(tmp_db):
    """
    Gap de un día entre conceptos → el streak se reinicia y solo cuenta desde hoy.

    Insertar conceptos hoy y hace 2 días (saltando ayer) → streak = 1
    (porque ayer no tiene concepto, el contador se detiene ahí).
    """
    user = create_user("ana", "password123")
    today = date.today()
    _insert_concept_on_date(tmp_db, user.id, "hoy",        today)
    _insert_concept_on_date(tmp_db, user.id, "hace_2",     today - timedelta(days=2))
    # ayer (today - 1) no tiene concepto → streak se rompe

    result = get_streak(user.id)
    assert result == 1, (
        f"Con gap en ayer, el streak solo cuenta hoy (1), obtuvo {result}"
    )


def test_today_count(tmp_db):
    """
    Conceptos de hoy se cuentan correctamente.
    Conceptos de días anteriores no se incluyen.
    """
    user = create_user("ana", "password123")
    today = date.today()
    yesterday = today - timedelta(days=1)

    _insert_concept_on_date(tmp_db, user.id, "hoy_1",    today)
    _insert_concept_on_date(tmp_db, user.id, "hoy_2",    today)
    _insert_concept_on_date(tmp_db, user.id, "ayer",     yesterday)

    result = get_today_count(user.id)
    assert result == 2, f"Deben contarse 2 conceptos de hoy, obtuvo {result}"


def test_daily_goal_default(tmp_db):
    """
    Usuario nuevo → get_daily_goal retorna 3 (valor por defecto).
    """
    user = create_user("ana", "password123")
    result = get_daily_goal(user.id)
    assert result == 3, f"La meta por defecto debe ser 3, obtuvo {result}"


def test_update_daily_goal(tmp_db):
    """
    Cambiar la meta a 5 → get_daily_goal retorna 5.
    """
    user = create_user("ana", "password123")
    update_daily_goal(user.id, 5)
    result = get_daily_goal(user.id)
    assert result == 5, f"Después de update_daily_goal(5), debe retornar 5, obtuvo {result}"
