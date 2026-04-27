"""
tests/test_sprint29.py
======================
Harness Sprint 29 — Tutor contextual y «Explícame más simple».
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")

import db.schema as _schema
from db.schema import init_db
from db.operations import create_user, save_last_tutor_response, get_last_tutor_response


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_nura.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def test_tutor_includes_user_context():
    """Cuando hay conceptos similares, el bloque del prompt contiene «ya conoces»."""
    from agents.tutor_agent import build_similar_concepts_prompt_section

    c = MagicMock()
    c.term = "Machine Learning"
    c.category = "IA"
    c.subcategory = ""

    section = build_similar_concepts_prompt_section(
        "¿Qué es machine learning y cómo se relaciona con la IA?",
        [c],
    )
    assert section, "Debe generarse un bloque de contexto cuando hay similitud."
    assert "ya conoces" in section.lower() or "ya conoce" in section.lower(), section


def test_tutor_no_context_when_empty():
    """Sin conceptos similares reales → no se añade el bloque de conexiones forzadas."""
    from agents.tutor_agent import build_similar_concepts_prompt_section

    assert build_similar_concepts_prompt_section("pregunta cualquiera", []) == ""

    c = MagicMock()
    c.term = "Término remoto"
    c.category = "Química"
    c.subcategory = ""
    # Pregunta sin solapamiento léxico ni de categoría
    out = build_similar_concepts_prompt_section(
        "zzzzzz xxxxxxx qqqqqq",
        [c],
    )
    assert out == "", f"No debe forzar contexto: {out!r}"


def test_simplify_returns_different_text():
    """simplify_explanation con Gemini mockeado retorna texto distinto al original."""
    from agents.tutor_agent import simplify_explanation

    original = "Texto largo y técnico " * 20
    simple_version = "Versión simple y corta para el usuario."

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key-for-mock"}, clear=False):
        with patch("agents.tutor_agent._call_gemini", return_value=simple_version):
            out = simplify_explanation(original, {})

    assert out == simple_version
    assert out != original


def test_simplify_fallback_on_error():
    """Si Gemini falla, simplify_explanation devuelve el texto original."""
    from agents.tutor_agent import simplify_explanation

    original = "Explicación original que debe preservarse."

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key-for-mock"}, clear=False):
        with patch("agents.tutor_agent._call_gemini", side_effect=RuntimeError("boom")):
            out = simplify_explanation(original, {})

    assert out == original


def test_simple_command_no_history(tmp_db):
    """/simple sin respuesta previa en BD → mensaje amigable."""
    from bot.handlers import handle_simple

    user = create_user("s29_nohist", "pass123456")
    out = handle_simple(99, user.id)
    assert "primero" in out.lower() or "pregunta" in out.lower(), out


def test_save_and_get_last_tutor_response(tmp_db):
    """save_last_tutor_response + get_last_tutor_response persisten correctamente."""
    user = create_user("s29_user", "pass123456")
    save_last_tutor_response(user.id, "Respuesta del tutor de prueba.")
    got = get_last_tutor_response(user.id)
    assert got == "Respuesta del tutor de prueba."
