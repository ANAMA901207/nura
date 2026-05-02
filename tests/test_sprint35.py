"""
tests/test_sprint35.py
======================
Sprint 35 — Experiencia y personalidad: historial conversacional, tutor, Telegram.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import time
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
    get_recent_conversation,
    save_conversation,
)


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_sprint35.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def test_conversation_history_table_exists(tmp_db):
    conn = sqlite3.connect(str(tmp_db))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='conversation_history'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None


def test_save_and_get_conversation(tmp_db):
    user = create_user("s35_hist", "secret123")
    save_conversation(user.id, "user", "Hola Nura")
    save_conversation(user.id, "nura", "Hola, ¿qué estudiamos?")
    rows = get_recent_conversation(user.id, limit=10)
    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert "Hola Nura" in rows[0]["content"]
    assert rows[1]["role"] == "nura"


def test_get_recent_conversation_respects_limit(tmp_db):
    user = create_user("s35_lim", "secret123")
    for i in range(7):
        save_conversation(user.id, "user", f"m{i}")
        time.sleep(0.003)
    got = get_recent_conversation(user.id, limit=5)
    assert len(got) == 5
    texts = [g["content"] for g in got]
    assert texts == ["m2", "m3", "m4", "m5", "m6"]


def test_tutor_system_prompt_has_personality():
    from agents.tutor_agent import TUTOR_SYSTEM_PROMPT

    low = TUTOR_SYSTEM_PROMPT.lower()
    assert "nura" in low
    assert "pregunta" in low


def test_greeting_response_has_profile_data(tmp_db):
    user = create_user("s35_greet", "secret123")
    from db.operations import set_telegram_id

    set_telegram_id(user.id, "555001")

    with patch("db.operations.get_concepts_due_today", return_value=[None, None, None]):
        from bot.handlers import handle_free_message

        out = asyncio.run(handle_free_message(555001, "hola"))

    assert "s35_greet" in out
    assert "3" in out
    assert "pendientes" in out.lower() or "repasar" in out.lower()


def test_conversation_saved_after_tutor_response(tmp_db):
    from langchain_core.messages import AIMessage

    user = create_user("s35_tutor", "secret123")

    mock_bound = MagicMock()
    mock_bound.invoke.return_value = AIMessage(content="Respuesta de prueba del tutor.")

    with (
        patch("agents.tutor_agent._call_gemini", return_value='{"needs_search": false}'),
        patch("agents.tutor_agent.get_all_concepts", return_value=[]),
        patch("agents.tutor_agent.web_search", return_value={"results": []}),
        patch("agents.tutor_agent.build_similar_concepts_prompt_section", return_value=""),
        patch("agents.tutor_agent.ChatGoogleGenerativeAI") as MockLLM,
        patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}),
        patch("tools.concept_detector_tool.detect_new_concepts", return_value=[]),
    ):
        MockLLM.return_value.bind_tools.return_value = mock_bound
        from agents.tutor_agent import tutor_agent

        tutor_agent(
            {
                "user_input": "¿Qué es SM-2?",
                "user_context": "",
                "mode": "question",
                "user_id": user.id,
                "user_profile": {},
                "sources": [],
                "diagram_svg": "",
                "suggested_concepts": [],
            }
        )

    hist = get_recent_conversation(user.id, limit=10)
    assert len(hist) == 2
    roles = [h["role"] for h in hist]
    assert roles == ["user", "nura"]
