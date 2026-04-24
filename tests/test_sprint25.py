"""
tests/test_sprint25.py
======================
Harness para Sprint 25 — Bot de Telegram con FastAPI.

Todos los tests usan mocks para aislar completamente las dependencias
externas (Telegram API, BD, LangGraph).  No se necesita red ni servidor real.

Casos
-----
1. test_health_endpoint_returns_ok
2. test_free_message_routes_to_tutor
3. test_capturar_command_detected
4. test_streak_command_detected
5. test_unlinked_user_gets_prompt
6. test_generate_link_code_six_digits
7. test_get_user_by_link_code_valid
8. test_get_user_by_link_code_expired
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Garantiza imports desde la raíz del proyecto
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Forzar modo SQLite en todos los tests
os.environ.setdefault("DATABASE_URL", "")


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_tg_update(text: str, telegram_id: int = 99, username: str = "tester") -> dict:
    """Construye un dict con la estructura mínima de un Update de Telegram."""
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": telegram_id, "username": username, "is_bot": False},
            "chat": {"id": telegram_id, "type": "private"},
            "text": text,
        },
    }


def _make_user_mock(user_id: int = 1, username: str = "ana") -> MagicMock:
    """Crea un mock de User con los campos mínimos."""
    user = MagicMock()
    user.id       = user_id
    user.username = username
    user.mastery_level = 2
    return user


# ── 1. Healthcheck ────────────────────────────────────────────────────────────

def test_health_endpoint_returns_ok():
    """GET /health → 200 {"status": "ok"}."""
    from fastapi.testclient import TestClient

    # Parchear el registro de webhook para no llamar a Telegram
    with patch("bot.main._register_webhook", return_value=None):
        from bot.main import app
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── 2. Mensaje libre → tutor ──────────────────────────────────────────────────

def test_free_message_routes_to_tutor():
    """
    Un mensaje sin '/' que no es un comando debe ser manejado por handle_free_message.
    """
    update = _make_tg_update("¿qué es la amortización?", telegram_id=42)

    mock_user = _make_user_mock(1, "ana")
    tutor_response = "La amortización es el proceso de…"

    with (
        patch("bot.handlers._get_linked_user", return_value=mock_user),
        patch("bot.nura_bridge.run_tutor", return_value=tutor_response),
    ):
        from bot.handlers import process_update
        result = process_update(update)

    assert result["handled"] is True
    assert tutor_response in result["text"]


# ── 3. /capturar detectado ────────────────────────────────────────────────────

def test_capturar_command_detected():
    """
    El texto '/capturar LangGraph' debe ser despachado a handle_capturar
    y devolver una respuesta que confirma la captura.
    """
    update = _make_tg_update("/capturar LangGraph", telegram_id=42)

    mock_user = _make_user_mock(1, "ana")
    tutor_response = "LangGraph es un framework para…"

    with (
        patch("bot.handlers._get_linked_user", return_value=mock_user),
        patch("bot.nura_bridge.run_tutor", return_value=tutor_response),
    ):
        from bot.handlers import process_update
        result = process_update(update)

    assert result["handled"] is True
    assert "LangGraph" in result["text"] or "capturado" in result["text"].lower()


# ── 4. /streak detectado ─────────────────────────────────────────────────────

def test_streak_command_detected():
    """
    El texto '/streak' debe ser despachado a handle_streak y devolver
    información sobre la racha del usuario.
    """
    update = _make_tg_update("/streak", telegram_id=42)

    mock_user = _make_user_mock(1, "ana")

    with (
        patch("bot.handlers._get_linked_user", return_value=mock_user),
        patch("db.operations.get_streak",       return_value=5),
        patch("db.operations.get_today_count",  return_value=2),
        patch("db.operations.get_daily_goal",   return_value=3),
    ):
        from bot.handlers import process_update
        result = process_update(update)

    assert result["handled"] is True
    text = result["text"]
    assert "5" in text           # días de streak
    assert "2" in text           # conceptos hoy
    assert "3" in text           # meta


# ── 5. Usuario no vinculado ───────────────────────────────────────────────────

def test_unlinked_user_gets_prompt():
    """
    Un telegram_id que no está vinculado debe recibir instrucciones
    de cómo vincular su cuenta, no un error.
    """
    update = _make_tg_update("hola", telegram_id=999)

    with patch("bot.handlers._get_linked_user", return_value=None):
        from bot.handlers import process_update
        result = process_update(update)

    assert result["handled"] is True
    text = result["text"].lower()
    assert "vincular" in text or "vincula" in text


# ── 6. Código de vinculación tiene 6 dígitos ─────────────────────────────────

def test_generate_link_code_six_digits():
    """
    generate_link_code() debe retornar una cadena de exactamente 6 dígitos.
    save_link_code se importa dentro de generate_link_code, así que se
    parchea en su módulo de origen: db.operations.
    """
    with patch("db.operations.save_link_code") as mock_save:
        from bot.nura_bridge import generate_link_code
        code = generate_link_code(user_id=1)

    assert len(code) == 6, f"El código debe tener 6 dígitos, tiene {len(code)}"
    assert code.isdigit(), f"El código debe ser numérico, obtuvo: {code!r}"
    mock_save.assert_called_once()


# ── 7. Código válido retorna usuario ─────────────────────────────────────────

def test_get_user_by_link_code_valid():
    """
    get_user_by_link_code con un código vigente debe retornar el User correcto.
    """
    import sqlite3
    import tempfile
    import db.schema as _schema
    from db.schema import init_db
    from db.operations import create_user, save_link_code, get_user_by_link_code

    with tempfile.TemporaryDirectory() as tmp:
        db_file = Path(tmp) / "test.db"
        original_path = _schema.DB_PATH
        _schema.DB_PATH = db_file
        os.environ["DATABASE_URL"] = ""

        try:
            init_db()
            user = create_user("ana", "pass123456")
            expiry = (datetime.now() + timedelta(minutes=10)).isoformat()
            save_link_code(user.id, "123456", expiry)

            found = get_user_by_link_code("123456")
        finally:
            _schema.DB_PATH = original_path

    assert found is not None, "Un código vigente debe retornar el usuario"
    assert found.id == user.id


# ── 8. Código expirado retorna None ──────────────────────────────────────────

def test_get_user_by_link_code_expired():
    """
    get_user_by_link_code con un código expirado debe retornar None.
    """
    import tempfile
    import db.schema as _schema
    from db.schema import init_db
    from db.operations import create_user, save_link_code, get_user_by_link_code

    with tempfile.TemporaryDirectory() as tmp:
        db_file = Path(tmp) / "test.db"
        original_path = _schema.DB_PATH
        _schema.DB_PATH = db_file
        os.environ["DATABASE_URL"] = ""

        try:
            init_db()
            user = create_user("ana", "pass123456")
            # Expiración en el pasado
            expiry = (datetime.now() - timedelta(minutes=5)).isoformat()
            save_link_code(user.id, "999999", expiry)

            found = get_user_by_link_code("999999")
        finally:
            _schema.DB_PATH = original_path

    assert found is None, "Un código expirado debe retornar None"
