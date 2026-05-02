"""
tests/test_sprint34_telegram_bugs.py
====================================
Sprint 34 — fixes Telegram + BD: texto plano del grafo, /examen robusto, /repaso vía review_agent.

Sin llamadas reales a Gemini ni a BD (solo mocks).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")


def _make_user_mock(user_id: int = 1, username: str = "ana") -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.username = username
    return user


# ── BUG-01: dict crudo → texto plano (nura_bridge.run_tutor) ───────────────────


def test_run_tutor_coerces_graph_output_key():
    """Mock del grafo retorna {'output': 'Hola'} → run_tutor devuelve 'Hola'."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"output": "Hola"}

    with (
        patch("db.operations.get_user_by_id", return_value=None),
        patch("agents.graph.build_graph", return_value=mock_graph),
    ):
        from bot.nura_bridge import run_tutor

        out = run_tutor(1, "hola")

    assert out == "Hola"
    assert not out.startswith("{")
    mock_graph.invoke.assert_called_once()


def test_coerce_graph_text_prefers_response_over_output():
    from bot.nura_bridge import _coerce_graph_text

    assert _coerce_graph_text({"response": "A", "output": "B"}) == "A"


# ── BUG-02: /examen args + errores ───────────────────────────────────────────


def test_args_after_command_with_bot_suffix():
    from bot.handlers import _args_after_command

    assert _args_after_command("/examen@NuraBot matematicas", "/examen") == "matematicas"
    assert _args_after_command("/examen matematicas", "/examen") == "matematicas"
    assert _args_after_command("/examen", "/examen") == ""
    assert _args_after_command("/examen@NuraBot", "/examen") == ""


def test_handle_examen_command_empty_category_lists_safe():
    """Sin categoría: lista categorías, sin excepción."""
    from bot import handlers

    uid = 42

    with patch.object(handlers, "_user_exam_categories", return_value=["Matemáticas"]):
        out = asyncio.run(handlers.handle_examen_command(0, uid, None))

    assert "Matemáticas" in out
    assert "`Matemáticas`" in out or "•" in out


def test_handle_examen_command_with_category_arg():
    """Con categoría resuelta: generate_exam mockeado → primera pregunta."""
    from bot import handlers

    uid = 7
    fake_qs = [
        {
            "question":   "Q1?",
            "options":    ["o1", "o2", "o3", "o4"],
            "correct":    "a",
            "concept":    "c1",
            "difficulty": "easy",
        }
    ] + [
        {
            "question":   f"Q{i}?",
            "options":    [f"a{i}", f"b{i}", f"c{i}", f"d{i}"],
            "correct":    "a",
            "concept":    f"c{i}",
            "difficulty": "easy",
        }
        for i in range(2, 11)
    ]

    class _C:
        term = "t"
        category = "IA"
        explanation = "e"
        is_classified = True
        flashcard_front = "f"

    with (
        patch.object(handlers, "_user_exam_categories", return_value=["IA"]),
        patch(
            "db.operations.get_all_concepts",
            return_value=[_C() for _ in range(5)],
        ),
        patch("db.operations.get_user_by_id", return_value=None),
        patch("db.operations.replace_exam_session"),
        patch("agents.exam_agent.generate_exam", return_value=fake_qs),
    ):
        out = asyncio.run(handlers.handle_examen_command(0, uid, "ia"))

    assert "Pregunta *1/10*" in out
    assert "http" not in out.lower()


def test_handle_examen_command_outer_exception_user_message():
    """Excepción fuera de generate_exam → mensaje legible."""
    from bot import handlers

    with patch.object(
        handlers,
        "_user_exam_categories",
        side_effect=RuntimeError("db down"),
    ):
        out = asyncio.run(handlers.handle_examen_command(0, 1, "x"))

    assert "No pude procesar" in out
    assert "RuntimeError" in out


def test_handle_examen_generate_exam_failure_message():
    """generate_exam lanza → mensaje específico de modelo."""
    from bot import handlers

    uid = 3

    class _C:
        term = "t"
        category = "IA"
        explanation = "e"
        is_classified = True
        flashcard_front = "f"

    with (
        patch.object(handlers, "_user_exam_categories", return_value=["IA"]),
        patch("db.operations.get_all_concepts", return_value=[_C()]),
        patch("db.operations.get_user_by_id", return_value=None),
        patch(
            "agents.exam_agent.generate_exam",
            side_effect=ValueError("quota"),
        ),
    ):
        out = asyncio.run(handlers.handle_examen_command(0, uid, "ia"))

    assert "No pude generar el examen" in out
    assert "ValueError" in out


# ── BUG-03: /repasar vía run_review ──────────────────────────────────────────


def test_handle_repasar_calls_run_review():
    mock_user = _make_user_mock(9, "bob")
    body = "SM-2 tiene *2* concepto(s) programado(s) para repasar hoy"

    with patch("bot.handlers._get_linked_user", return_value=mock_user):
        from bot import handlers

        with patch("bot.nura_bridge.run_review", return_value=body) as rr:
            out = handlers.handle_repasar(1)

    rr.assert_called_once_with(9)
    assert out == body


def test_handle_repasar_response_has_no_http():
    mock_user = _make_user_mock(2, "u")

    with patch("bot.handlers._get_linked_user", return_value=mock_user):
        from bot import handlers

        with patch(
            "bot.nura_bridge.run_review",
            return_value="SM-2 tiene 1 concepto(s) programado(s) para repasar hoy:\n\n• **X**",
        ):
            out = handlers.handle_repasar(99)

    assert "http" not in out.lower()


def test_handle_repasar_unlinked_instruction_has_no_http():
    from bot import handlers

    with patch("bot.handlers._get_linked_user", return_value=None):
        out = handlers.handle_repasar(1)

    assert "http" not in out.lower()
    assert "vincul" in out.lower() or "Vincular" in out


def test_run_review_coerces_output_and_no_http():
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "output": "Tu base de conocimiento está vacía. Capturá términos primero.",
    }

    with (
        patch("db.operations.get_user_by_id", return_value=None),
        patch("agents.graph.build_graph", return_value=mock_graph),
    ):
        from bot.nura_bridge import run_review

        txt = run_review(5)

    assert "http" not in txt.lower()
    assert "vacía" in txt.lower()


def test_process_update_examen_with_botname_prefix():
    """Update con /examen@Bot categoría → categoría llega al handler."""
    from bot import handlers

    update = {
        "message": {
            "message_id": 1,
            "from": {"id": 100, "username": "t", "is_bot": False},
            "chat": {"id": 100, "type": "private"},
            "text": "/examen@NuraBot Matemáticas",
        },
    }
    mock_user = _make_user_mock(1, "ana")
    captured: dict = {}

    async def _fake_exam(_tid, uid, cat):
        captured["cat"] = cat
        return "OK"

    with (
        patch("bot.handlers._get_linked_user", return_value=mock_user),
        patch("bot.handlers.try_handle_exam_answer", return_value=None),
        patch("bot.handlers.handle_examen_command", side_effect=_fake_exam),
    ):
        result = asyncio.run(handlers.process_update(update))

    assert result["handled"] is True
    assert captured.get("cat") == "Matemáticas"
    assert result["text"] == "OK"
