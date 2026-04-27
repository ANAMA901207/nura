"""
tests/test_sprint30.py
======================
Harness Sprint 30 — Examen y certificación por categoría.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from datetime import datetime
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
    get_best_score,
    get_certifications,
    save_certification,
)


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_nura30.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def test_certifications_table_exists(tmp_db):
    conn = sqlite3.connect(str(tmp_db))
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='certifications'"
        )
        assert cur.fetchone() is not None
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='exam_sessions'"
        )
        assert cur.fetchone() is not None
    finally:
        conn.close()


def test_save_and_get_certification(tmp_db):
    uid = create_user("u30", "x" * 60).id
    save_certification(uid, "IA", 0.9, True)
    save_certification(uid, "IA", 0.5, False)
    rows = get_certifications(uid)
    assert len(rows) == 2
    by_score = {round(r["score"], 2): r for r in rows}
    assert by_score[0.9]["passed"] is True
    assert by_score[0.5]["passed"] is False
    assert all(r["category"] == "IA" for r in rows)


def test_get_best_score(tmp_db):
    uid = create_user("u31", "y" * 60).id
    save_certification(uid, "Finanzas", 0.7, False)
    save_certification(uid, "Finanzas", 0.85, True)
    assert abs((get_best_score(uid, "Finanzas") or 0) - 0.85) < 1e-6
    assert get_best_score(uid, "Inexistente") is None


def test_exam_agent_generates_questions():
    from agents import exam_agent

    fake = [
        {
            "question":   f"Q{i}?",
            "options":    [f"A{i}", f"B{i}", f"C{i}", f"D{i}"],
            "correct":    "a",
            "concept":    f"C{i}",
            "difficulty": ["easy", "easy", "easy", "medium", "medium", "medium", "medium", "hard", "hard", "hard"][i],
        }
        for i in range(10)
    ]
    raw = __import__("json").dumps(fake)

    class _Resp:
        content = raw

    class _LLM:
        def invoke(self, messages):
            return _Resp()

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "k"}, clear=False):
        with patch.object(exam_agent, "ChatGoogleGenerativeAI", return_value=_LLM()):
            out = exam_agent.generate_exam("IA", [{"term": "x"}], {})
    assert len(out) == 10
    assert out[0]["question"].startswith("Q0")


def test_exam_agent_questions_have_options():
    from agents.exam_agent import evaluate_exam

    qs = [
        {
            "question":   "q",
            "options":    ["o1", "o2", "o3", "o4"],
            "correct":    "b",
            "concept":    "c",
            "difficulty": "easy",
        }
        for _ in range(10)
    ]
    for q in qs:
        assert len(q["options"]) == 4
    r = evaluate_exam(qs, ["b"] * 10)
    assert r["total"] == 10


def test_passed_when_score_above_threshold():
    from agents.exam_agent import evaluate_exam

    qs = [
        {"question": "q", "options": ["a", "b", "c", "d"], "correct": "a", "concept": "k"}
    ] * 10
    answers = ["a"] * 8 + ["b", "b"]
    r = evaluate_exam(qs, answers)
    assert r["correct"] == 8
    assert r["passed"] is True


def test_failed_when_score_below_threshold():
    from agents.exam_agent import evaluate_exam

    qs = [
        {"question": "q", "options": ["a", "b", "c", "d"], "correct": "a", "concept": "k"}
    ] * 10
    answers = ["a"] * 7 + ["b", "b", "b"]
    r = evaluate_exam(qs, answers)
    assert r["correct"] == 7
    assert r["passed"] is False


def test_examen_command_no_category(tmp_db):
    from bot import handlers

    uid = create_user("tg30", "z" * 60).id
    created_at = datetime.now().isoformat()
    conn = sqlite3.connect(str(_schema.DB_PATH))
    try:
        conn.execute(
            """INSERT INTO concepts
               (term, category, subcategory, explanation, examples, analogy,
                context, flashcard_front, flashcard_back, mastery_level,
                created_at, is_classified, user_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "t1",
                "IA",
                "",
                "e",
                "",
                "",
                "",
                "f",
                "b",
                1,
                created_at,
                1,
                uid,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    mock_user = MagicMock()
    mock_user.id = uid

    with patch.object(handlers, "_get_linked_user", return_value=mock_user):
        out = asyncio.run(handlers.handle_examen_command(0, uid, ""))

    assert "Categorías disponibles" in out or "categoría" in out.lower()
    assert "IA" in out
