"""
tests/test_sprint27.py
======================
Harness para Sprint 27 — Audio / podcast por Telegram.

Verifica:
- generate_podcast_text: retorna string no vacío.
- generate_podcast_text: contiene "Hola" (saludo al usuario).
- /podcast  → handle_podcast invocado.
- /audio LangGraph → handle_audio invocado con term="LangGraph".
- /audio sin término → mensaje de error amigable.
- text_to_speech con mock de gTTS/pydub → retorna bytes no vacíos.

Estrategia de aislamiento
-------------------------
- TTS y las llamadas de red se mockean siempre: sin gTTS real, sin red.
- Las funciones de BD se mockean con patch para no necesitar SQLite.
- Los handlers de Telegram se testean a través de process_update (async → asyncio.run).
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")

# ── Stub de pydub para Python 3.13+ (audioop fue removido) ───────────────────
# pydub falla al importarse en Python 3.13/3.14 por 'audioop' inexistente.
# Inyectamos un stub vacío en sys.modules para que:
#   1. `from pydub import AudioSegment` dentro de text_to_speech no explote.
#   2. Los tests puedan controlar AudioSegment con patch normal.
# Esto NO afecta a Railway (donde pydub funciona con audioop del sistema).
if "pydub" not in sys.modules:
    _pydub_stub = MagicMock()
    sys.modules["pydub"] = _pydub_stub
    sys.modules["pydub.audio_segment"] = _pydub_stub
    sys.modules["pydub.utils"] = _pydub_stub


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_tg_update(text: str, telegram_id: int = 42, username: str = "tester") -> dict:
    """Construye un Update de Telegram mínimo."""
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
    return user


# ── 1. generate_podcast_text: no vacío ───────────────────────────────────────

def test_generate_podcast_text_not_empty():
    """generate_podcast_text con mocks de BD → string no vacío."""
    from bot.tts import generate_podcast_text

    mock_concept = MagicMock()
    mock_concept.term       = "LangGraph"
    mock_concept.created_at = "2026-04-24T20:00:00"

    with (
        patch("db.operations.get_today_count",  return_value=2),
        patch("db.operations.get_daily_goal",   return_value=5),
        patch("bot.nura_bridge.get_pending_concepts", return_value=[]),
        patch("db.operations.get_all_concepts", return_value=[mock_concept]),
    ):
        text = generate_podcast_text(1)

    assert isinstance(text, str)
    assert len(text.strip()) > 0, "generate_podcast_text no debe retornar cadena vacía."


# ── 2. generate_podcast_text: contiene saludo ─────────────────────────────────

def test_generate_podcast_text_has_greeting():
    """El texto del podcast debe contener un saludo ('Hola')."""
    from bot.tts import generate_podcast_text

    with (
        patch("db.operations.get_today_count",  return_value=1),
        patch("db.operations.get_daily_goal",   return_value=3),
        patch("bot.nura_bridge.get_pending_concepts", return_value=[]),
        patch("db.operations.get_all_concepts", return_value=[]),
    ):
        text = generate_podcast_text(1)

    assert "Hola" in text, f"El podcast debe empezar con un saludo. Texto: {text!r}"


# ── 3. /podcast → handle_podcast invocado ────────────────────────────────────

def test_podcast_command_detected():
    """
    El comando '/podcast' en process_update debe invocar handle_podcast.
    Se usa AsyncMock para reemplazar el handler y verificar la llamada.
    """
    update = _make_tg_update("/podcast", telegram_id=42)
    mock_user = _make_user_mock(1, "ana")

    expected = {
        "chat_id":     42,
        "audio_bytes": b"fake_ogg",
        "type":        "voice",
        "handled":     True,
    }

    with (
        patch("bot.handlers._get_linked_user", return_value=mock_user),
        patch("bot.handlers.handle_podcast", new_callable=AsyncMock) as mock_h,
    ):
        mock_h.return_value = expected
        from bot.handlers import process_update
        result = asyncio.run(process_update(update))

    mock_h.assert_called_once_with(42, mock_user.id)
    assert result["type"] == "voice"
    assert result["handled"] is True


# ── 4. /audio LangGraph → handle_audio con term correcto ─────────────────────

def test_audio_command_with_term():
    """
    '/audio LangGraph' debe invocar handle_audio con term='LangGraph'.
    """
    update = _make_tg_update("/audio LangGraph", telegram_id=42)
    mock_user = _make_user_mock(1, "ana")

    expected = {
        "chat_id":     42,
        "audio_bytes": b"fake_ogg",
        "type":        "voice",
        "handled":     True,
    }

    with (
        patch("bot.handlers._get_linked_user", return_value=mock_user),
        patch("bot.handlers.handle_audio", new_callable=AsyncMock) as mock_h,
    ):
        mock_h.return_value = expected
        from bot.handlers import process_update
        result = asyncio.run(process_update(update))

    mock_h.assert_called_once_with(42, mock_user.id, "LangGraph")
    assert result["type"] == "voice"
    assert result["handled"] is True


# ── 5. /audio sin término → mensaje de error amigable ────────────────────────

def test_audio_command_no_term():
    """
    handle_audio con term vacío debe retornar un mensaje de error amigable,
    sin llamar a la IA ni a TTS.
    """
    from bot.handlers import handle_audio

    result = asyncio.run(handle_audio(42, 1, ""))

    assert result["handled"] is True
    assert result["type"] == "text"
    text = result["text"].lower()
    assert "audio" in text or "término" in text or "escribe" in text, (
        f"El mensaje de error debe ser informativo. Texto: {result['text']!r}"
    )


# ── 6. text_to_speech con mock → bytes no vacíos ─────────────────────────────

def test_tts_returns_bytes():
    """
    text_to_speech con gTTS y AudioSegment mockeados debe retornar bytes no vacíos.
    No se hace ninguna llamada de red ni se necesita ffmpeg.

    Estrategia: pydub ya está en sys.modules como MagicMock (stub de módulo).
    Mockeamos gtts.gTTS y pydub.AudioSegment (alias de sys.modules["pydub"].AudioSegment)
    para controlar el flujo completo dentro de text_to_speech.
    """
    from bot.tts import text_to_speech

    fake_ogg = b"fake_ogg_audio_data"

    def _fake_write_to_fp(fp):
        fp.write(b"fake_mp3_data")

    mock_tts_instance = MagicMock()
    mock_tts_instance.write_to_fp.side_effect = _fake_write_to_fp

    mock_audio = MagicMock()

    def _fake_export(fp, **kwargs):
        fp.write(fake_ogg)

    mock_audio.export.side_effect = _fake_export
    mock_audio_segment_cls = MagicMock()
    mock_audio_segment_cls.from_mp3.return_value = mock_audio

    # gtts también puede estar parcialmente disponible; lo mockeamos en su módulo
    mock_gtts_module = MagicMock()
    mock_gtts_module.gTTS.return_value = mock_tts_instance

    with (
        patch.dict(sys.modules, {"gtts": mock_gtts_module}),
        patch.dict(sys.modules, {"pydub": MagicMock(AudioSegment=mock_audio_segment_cls)}),
    ):
        result = text_to_speech("Hola, esto es una prueba de audio.")

    assert isinstance(result, bytes), "text_to_speech debe retornar bytes."
    assert len(result) > 0, "text_to_speech no debe retornar bytes vacíos."
    assert result == fake_ogg
