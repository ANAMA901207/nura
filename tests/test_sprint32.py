"""
tests/test_sprint32.py
======================
Harness Sprint 32 — Perfil de aprendizaje visible.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")

import db.schema as _schema
from db.schema import init_db
from db.operations import (
    create_user,
    get_activity_last_30_days,
    get_max_streak,
    get_user_stats,
    save_concept,
)


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_nura32.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def test_get_user_stats_structure(tmp_db):
    uid = create_user("st32", "p" * 60).id
    for i in range(6):
        save_concept(f"T{i}", user_id=uid)
    stats = get_user_stats(uid)
    assert set(stats.keys()) == {
        "total_concepts",
        "total_connections",
        "top_categories",
        "current_streak",
        "max_streak",
        "certifications_count",
        "mastery_pct",
        "certifications",
    }
    assert isinstance(stats["top_categories"], list)
    assert isinstance(stats["certifications"], list)


def test_get_user_stats_empty_user(tmp_db):
    uid = create_user("empty32", "q" * 60).id
    s = get_user_stats(uid)
    assert s["total_concepts"] == 0
    assert s["total_connections"] == 0
    assert s["top_categories"] == []
    assert s["certifications_count"] == 0
    assert s["mastery_pct"] == 0.0


def test_get_max_streak_empty(tmp_db):
    uid = create_user("mx0", "r" * 60).id
    assert get_max_streak(uid) == 0


def test_get_max_streak_with_data(tmp_db):
    uid = create_user("mx5", "s" * 60).id
    today = date.today()
    conn = sqlite3.connect(str(tmp_db))
    try:
        for i in range(5):
            d = (today - timedelta(days=4 - i)).isoformat()
            conn.execute(
                """INSERT INTO concepts
                   (term, category, subcategory, explanation, examples, analogy,
                    context, flashcard_front, flashcard_back, mastery_level,
                    created_at, is_classified, user_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"D{i}",
                    "IA",
                    "",
                    " ",
                    "",
                    "",
                    "",
                    "",
                    "",
                    0,
                    f"{d}T12:00:00",
                    0,
                    uid,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    assert get_max_streak(uid) == 5


def test_get_activity_last_30_days_structure(tmp_db):
    uid = create_user("act32", "t" * 60).id
    rows = get_activity_last_30_days(uid)
    assert len(rows) == 30
    for r in rows:
        assert set(r.keys()) == {"date", "count"}
        assert len(r["date"]) == 10
        assert r["date"][4] == "-"
        assert isinstance(r["count"], int)
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates)


def test_perfil_command_telegram(tmp_db):
    from bot.handlers import handle_perfil

    uid = create_user("pf1", "u" * 60).id
    save_concept("Algo", user_id=uid)
    out = handle_perfil(0, uid)
    assert "perfil" in out.lower()
    assert "Conceptos" in out or "conceptos" in out.lower()
    assert "1" in out


def test_render_profile_no_crash():
    import ui.components as comp

    def _col():
        c = MagicMock()
        c.__enter__ = MagicMock(return_value=c)
        c.__exit__ = MagicMock(return_value=False)
        return c

    cols = [_col() for _ in range(4)]
    with patch("streamlit.columns", return_value=cols):
        with patch("streamlit.metric"):
            with patch("streamlit.caption"):
                with patch("streamlit.markdown"):
                    with patch("streamlit.progress"):
                        with patch.object(comp, "render_certification_badge"):
                            comp.render_profile(
                                {
                                    "total_concepts":        10,
                                    "total_connections":     2,
                                    "top_categories":        [{"category": "IA", "count": 8}],
                                    "current_streak":        1,
                                    "max_streak":            3,
                                    "certifications_count":  0,
                                    "mastery_pct":           40.0,
                                    "certifications":        [],
                                }
                            )
