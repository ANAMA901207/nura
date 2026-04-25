"""
tests/test_sprint26.py
======================
Harness para Sprint 26 — Alertas automáticas por Telegram.

Verifica:
- get_reminder_time: usuario nuevo → "20:00".
- set_reminder_time: guardar "08:00" → get retorna "08:00".
- set_reminder_time: "25:00" → ValueError.
- get_users_to_remind: usuario con reminder_time actual y today_count < goal → aparece.
- get_users_to_remind: usuario que ya cumplió meta → no aparece.
- mensaje de recordatorio: contiene nombre y números correctos.

Estrategia de fixture
---------------------
Cada test usa una BD SQLite temporal aislada (tmp_path) con DATABASE_URL="".
Los usuarios se crean con create_user(); para controlar today_count se insertan
conceptos directamente con SQLite.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

import db.schema as _schema
from db.schema import init_db
from db.operations import (
    create_user,
    get_reminder_time,
    set_reminder_time,
    get_users_to_remind,
    set_telegram_id,
)
from bot.scheduler import _build_reminder_message


# ── fixture: BD aislada por test ──────────────────────────────────────────────

@pytest.fixture()
def tmp_db(tmp_path):
    """
    Crea una BD SQLite temporal para cada test.

    Sobreescribe db.schema.DB_PATH y fuerza modo SQLite (DATABASE_URL="").
    Restaura los valores originales al terminar.
    """
    db_file = tmp_path / "test_nura.db"
    original_path = _schema.DB_PATH
    original_url  = os.environ.get("DATABASE_URL", "")

    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""

    init_db()

    yield db_file

    _schema.DB_PATH = original_path
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def _insert_concept_today(db_path: Path, user_id: int, term: str) -> None:
    """Inserta un concepto creado hoy para controlar today_count en tests."""
    created_at = datetime.combine(date.today(), datetime.min.time()).isoformat()
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


def _set_reminder_db(db_path: Path, user_id: int, reminder_time: str) -> None:
    """Establece reminder_time directamente en la BD para preparar tests."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE users SET reminder_time = ? WHERE id = ?",
            (reminder_time, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _set_telegram_db(db_path: Path, user_id: int, telegram_id: str) -> None:
    """Vincula telegram_id directamente en la BD para preparar tests."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE users SET telegram_id = ? WHERE id = ?",
            (telegram_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_get_reminder_time_default(tmp_db):
    """Usuario nuevo sin reminder_time explícito → debe retornar '20:00'."""
    user = create_user("user_default", "pass123")
    result = get_reminder_time(user.id)
    assert result == "20:00", f"Se esperaba '20:00', se obtuvo '{result}'"


def test_set_reminder_time(tmp_db):
    """Guardar '08:00' y luego leer → debe retornar '08:00'."""
    user = create_user("user_set", "pass123")
    set_reminder_time(user.id, "08:00")
    result = get_reminder_time(user.id)
    assert result == "08:00", f"Se esperaba '08:00', se obtuvo '{result}'"


def test_set_reminder_time_invalid(tmp_db):
    """Formato '25:00' → debe lanzar ValueError."""
    user = create_user("user_invalid", "pass123")
    with pytest.raises(ValueError):
        set_reminder_time(user.id, "25:00")


def test_get_users_to_remind_matches_time(tmp_db):
    """
    Usuario con reminder_time == hora_actual y today_count < daily_goal
    → debe aparecer en get_users_to_remind.
    """
    from datetime import datetime as _dt
    current_time = _dt.now().strftime("%H:%M")

    user = create_user("user_remind", "pass123")
    _set_telegram_db(tmp_db, user.id, "123456789")
    _set_reminder_db(tmp_db, user.id, current_time)

    users = get_users_to_remind(current_time)
    ids = [u.id for u in users]
    assert user.id in ids, (
        f"Se esperaba que user_id={user.id} estuviera en la lista de recordatorios, "
        f"pero los ids encontrados fueron: {ids}"
    )


def test_get_users_to_remind_excludes_completed(tmp_db):
    """
    Usuario que ya cumplió su meta (today_count >= daily_goal)
    → NO debe aparecer en get_users_to_remind.
    """
    from datetime import datetime as _dt
    current_time = _dt.now().strftime("%H:%M")

    user = create_user("user_done", "pass123")
    _set_telegram_db(tmp_db, user.id, "987654321")
    _set_reminder_db(tmp_db, user.id, current_time)

    conn = sqlite3.connect(str(tmp_db))
    try:
        conn.execute("UPDATE users SET daily_goal = 2 WHERE id = ?", (user.id,))
        conn.commit()
    finally:
        conn.close()

    _insert_concept_today(tmp_db, user.id, "concept_a")
    _insert_concept_today(tmp_db, user.id, "concept_b")

    users = get_users_to_remind(current_time)
    ids = [u.id for u in users]
    assert user.id not in ids, (
        f"user_id={user.id} no debería estar en la lista (ya cumplió meta), "
        f"pero se encontró en: {ids}"
    )


def test_reminder_message_format(tmp_db):
    """
    El mensaje generado debe contener el nombre del usuario,
    today_count y daily_goal correctamente.
    """
    username   = "ana"
    today      = 2
    goal       = 5
    pending    = 3

    msg = _build_reminder_message(username, today, goal, pending)

    assert username  in msg, "El mensaje debe contener el nombre del usuario."
    assert str(today) in msg, "El mensaje debe contener today_count."
    assert str(goal)  in msg, "El mensaje debe contener daily_goal."
    assert str(pending) in msg, "El mensaje debe contener pending."
