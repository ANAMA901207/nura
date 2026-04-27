"""
tests/test_sprint31.py
======================
Harness Sprint 31 — Brechas y progreso por área.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")

import db.schema as _schema
from db.schema import init_db
from db.operations import (
    create_user,
    get_concepts_by_week,
    get_orphan_concepts,
    save_connection,
    save_concept,
)


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_nura31.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def test_get_orphan_concepts_returns_isolated(tmp_db):
    uid = create_user("orph1", "p" * 60).id
    save_concept("Solo", user_id=uid)
    orphans = get_orphan_concepts(uid)
    assert len(orphans) >= 1
    terms = {o["term"] for o in orphans}
    assert "Solo" in terms


def test_get_orphan_concepts_excludes_connected(tmp_db):
    uid = create_user("orph2", "q" * 60).id
    a = save_concept("NodoA", user_id=uid)
    b = save_concept("NodoB", user_id=uid)
    save_connection(a.id, b.id, user_id=uid)
    orphans = get_orphan_concepts(uid)
    terms = {o["term"] for o in orphans}
    assert "NodoA" not in terms
    assert "NodoB" not in terms


def test_get_concepts_by_week_structure(tmp_db):
    uid = create_user("wk1", "r" * 60).id
    import sqlite3

    conn = sqlite3.connect(str(tmp_db))
    try:
        conn.execute(
            """INSERT INTO concepts
               (term, category, subcategory, explanation, examples, analogy,
                context, flashcard_front, flashcard_back, mastery_level,
                created_at, is_classified, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "C1",
                "IA",
                "",
                " ",
                "",
                "",
                "",
                "",
                "",
                0,
                "2026-01-05T10:00:00",
                0,
                uid,
            ),
        )
        conn.execute(
            """INSERT INTO concepts
               (term, category, subcategory, explanation, examples, analogy,
                context, flashcard_front, flashcard_back, mastery_level,
                created_at, is_classified, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "C2",
                "IA",
                "",
                " ",
                "",
                "",
                "",
                "",
                "",
                0,
                "2026-01-19T12:00:00",
                0,
                uid,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    rows = get_concepts_by_week(uid)
    assert isinstance(rows, list)
    assert len(rows) > 0
    for r in rows:
        assert set(r.keys()) == {"week", "category", "count"}
        assert isinstance(r["week"], str)
        assert isinstance(r["category"], str)
        assert isinstance(r["count"], int)
    weeks = [r["week"] for r in rows]
    assert weeks == sorted(weeks)


def test_get_concepts_by_week_empty(tmp_db):
    uid = create_user("empty31", "s" * 60).id
    assert get_concepts_by_week(uid) == []


def test_brechas_command_no_orphans(tmp_db):
    from bot.handlers import handle_brechas

    uid = create_user("br1", "t" * 60).id
    out = handle_brechas(0, uid)
    assert "bien conectado" in out.lower()


def test_brechas_command_with_orphans(tmp_db):
    from bot.handlers import handle_brechas

    uid = create_user("br2", "u" * 60).id
    save_concept("LangGraph", user_id=uid)
    out = handle_brechas(0, uid)
    assert "LangGraph" in out
    assert "/tutor" in out
    assert "relaciona" in out.lower()
