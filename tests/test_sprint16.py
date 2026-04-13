"""
tests/test_sprint16.py
======================
Harness del Sprint 16 — mensaje motivador híbrido al final de sesión.

Verifica:
1. Lógica determinista selecciona 'primera_sesion' cuando es_primera_sesion=True.
2. Lógica selecciona 'racha_7' cuando racha >= 7 (y no es primera sesión).
3. Mensaje de respaldo no está vacío para cada tipo de evento.
4. get_session_stats retorna dict con todos los campos requeridos.
5. render_motivational_banner no lanza errores con mensaje válido.
"""

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Añadir raíz del proyecto al path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestDeterministicLogic(unittest.TestCase):
    """Tests de la lógica determinista de _determine_event_type."""

    def setUp(self):
        """Importa las funciones del agente motivador."""
        from agents.motivator_agent import _determine_event_type, _fallback_message
        self._det = _determine_event_type
        self._fb  = _fallback_message

    def test_primera_sesion_selected_when_flag_true(self):
        """
        (1) Lógica determinista selecciona 'primera_sesion' cuando
        es_primera_sesion=True, independientemente de otros valores.
        """
        stats = {
            "es_primera_sesion": True,
            "racha":             10,
            "conexiones_hoy":    5,
            "conceptos_hoy":     5,
            "repasados_hoy":     0,
            "quiz_score":        None,
        }
        self.assertEqual(self._det(stats), "primera_sesion")

    def test_racha_7_selected_when_racha_gte_7(self):
        """
        (2) Lógica selecciona 'racha_7' cuando racha >= 7 y no es primera sesión.
        """
        stats = {
            "es_primera_sesion": False,
            "racha":             8,
            "conexiones_hoy":    1,
            "conceptos_hoy":     2,
            "repasados_hoy":     0,
            "quiz_score":        None,
        }
        self.assertEqual(self._det(stats), "racha_7")

    def test_racha_7_not_selected_below_threshold(self):
        """racha < 7 no activa racha_7."""
        stats = {
            "es_primera_sesion": False,
            "racha":             6,
            "conexiones_hoy":    0,
            "conceptos_hoy":     0,
            "repasados_hoy":     3,
            "quiz_score":        None,
        }
        event = self._det(stats)
        self.assertNotEqual(event, "racha_7")

    def test_conexiones_3_selected(self):
        """conexiones_hoy >= 3 activa conexiones_3 (cuando no hay prioridad mayor)."""
        stats = {
            "es_primera_sesion": False,
            "racha":             2,
            "conexiones_hoy":    4,
            "conceptos_hoy":     2,
            "repasados_hoy":     0,
            "quiz_score":        None,
        }
        self.assertEqual(self._det(stats), "conexiones_3")

    def test_quiz_bajo_selected_when_score_low(self):
        """quiz_score < 60 activa quiz_bajo (cuando no hay prioridad mayor)."""
        stats = {
            "es_primera_sesion": False,
            "racha":             1,
            "conexiones_hoy":    0,
            "conceptos_hoy":     2,
            "repasados_hoy":     0,
            "quiz_score":        40.0,
        }
        self.assertEqual(self._det(stats), "quiz_bajo")

    def test_default_fallback(self):
        """Sesión normal sin evento destacado retorna 'default'."""
        stats = {
            "es_primera_sesion": False,
            "racha":             1,
            "conexiones_hoy":    0,
            "conceptos_hoy":     2,
            "repasados_hoy":     0,
            "quiz_score":        None,
        }
        self.assertEqual(self._det(stats), "default")


class TestFallbackMessages(unittest.TestCase):
    """(3) Los mensajes de respaldo no están vacíos para ningún tipo."""

    _TYPES = [
        "primera_sesion",
        "racha_7",
        "conexiones_3",
        "conceptos_5",
        "solo_repaso",
        "quiz_bajo",
        "default",
    ]

    def test_all_fallback_messages_non_empty(self):
        """Cada tipo de evento tiene un mensaje de respaldo no vacío."""
        from agents.motivator_agent import _fallback_message
        for event_type in self._TYPES:
            with self.subTest(event_type=event_type):
                msg = _fallback_message(event_type)
                self.assertIsInstance(msg, str)
                self.assertTrue(len(msg.strip()) > 0, f"Mensaje vacío para '{event_type}'")

    def test_unknown_type_returns_default(self):
        """Un tipo desconocido retorna el mensaje de 'default'."""
        from agents.motivator_agent import _fallback_message, _FALLBACK
        msg = _fallback_message("tipo_inexistente")
        self.assertEqual(msg, _FALLBACK["default"])


class TestGetSessionStats(unittest.TestCase):
    """(4) get_session_stats retorna dict con todos los campos requeridos."""

    _REQUIRED_KEYS = {
        "conceptos_hoy",
        "conexiones_hoy",
        "repasados_hoy",
        "racha",
        "es_primera_sesion",
        "quiz_score",
    }

    def test_returns_all_required_fields(self):
        """get_session_stats devuelve un dict con los 6 campos especificados."""
        with patch("db.operations.get_connection") as mock_conn:
            # Simular daily_summaries vacía
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.lastrowid = 1

            mock_execute = MagicMock()
            mock_execute.fetchone.return_value = {
                "id": 1, "date": "2026-01-01",
                "concepts_captured": 2, "new_connections": 1,
                "concepts_reviewed": 0, "user_id": 1,
            }
            mock_execute.lastrowid = 1

            conn_ctx = MagicMock()
            conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
            conn_ctx.__exit__  = MagicMock(return_value=False)
            conn_ctx.execute   = MagicMock(return_value=mock_execute)
            mock_conn.return_value = conn_ctx

            with patch("db.operations.get_all_concepts", return_value=[]):
                from db.operations import get_session_stats
                result = get_session_stats(user_id=1)

        self.assertIsInstance(result, dict)
        missing = self._REQUIRED_KEYS - set(result.keys())
        self.assertEqual(missing, set(), f"Faltan claves: {missing}")

    def test_quiz_score_is_none_by_default(self):
        """quiz_score siempre es None en el retorno de get_session_stats."""
        with patch("db.operations.get_connection") as mock_conn:
            mock_execute = MagicMock()
            mock_execute.fetchone.return_value = {
                "id": 1, "date": "2026-01-01",
                "concepts_captured": 0, "new_connections": 0,
                "concepts_reviewed": 0, "user_id": 1,
            }
            mock_execute.lastrowid = 1
            conn_ctx = MagicMock()
            conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
            conn_ctx.__exit__  = MagicMock(return_value=False)
            conn_ctx.execute   = MagicMock(return_value=mock_execute)
            mock_conn.return_value = conn_ctx

            with patch("db.operations.get_all_concepts", return_value=[]):
                from db.operations import get_session_stats
                result = get_session_stats(user_id=1)

        self.assertIsNone(result["quiz_score"])

    def test_es_primera_sesion_true_when_all_concepts_captured_today(self):
        """es_primera_sesion=True cuando total_conceptos == conceptos_hoy."""
        with patch("db.operations.get_connection") as mock_conn:
            mock_execute = MagicMock()
            mock_execute.fetchone.return_value = {
                "id": 1, "date": "2026-01-01",
                "concepts_captured": 3, "new_connections": 0,
                "concepts_reviewed": 0, "user_id": 1,
            }
            mock_execute.lastrowid = 1
            conn_ctx = MagicMock()
            conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
            conn_ctx.__exit__  = MagicMock(return_value=False)
            conn_ctx.execute   = MagicMock(return_value=mock_execute)
            mock_conn.return_value = conn_ctx

            # Solo 3 conceptos en total, igual que conceptos_hoy
            fake_concepts = [MagicMock(), MagicMock(), MagicMock()]
            with patch("db.operations.get_all_concepts", return_value=fake_concepts):
                from db.operations import get_session_stats
                result = get_session_stats(user_id=1)

        self.assertTrue(result["es_primera_sesion"])


class TestRenderMotivationalBanner(unittest.TestCase):
    """(5) render_motivational_banner no lanza errores con mensaje válido."""

    def test_renders_without_error_with_valid_message(self):
        """render_motivational_banner no lanza ninguna excepción."""
        import streamlit as st
        mock_st = MagicMock()

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            # Re-importar para usar el mock
            import importlib
            import ui.components as comp
            importlib.reload(comp)
            try:
                comp.render_motivational_banner("Tu primera estrella en el mapa.")
            except Exception as exc:
                self.fail(f"render_motivational_banner lanzó excepción: {exc}")

    def test_renders_nothing_for_empty_message(self):
        """render_motivational_banner no llama a st.markdown si message está vacío."""
        mock_st = MagicMock()
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            import importlib
            import ui.components as comp
            importlib.reload(comp)
            comp.render_motivational_banner("")
            mock_st.markdown.assert_not_called()

    def test_message_content_is_escaped(self):
        """El mensaje se escapa con html.escape() — el tag <script> no aparece literal.

        Sprint 22: render_motivational_toast usa st.markdown con HTML fijo.
        El contenido del mensaje se escapa antes de embeberse, evitando XSS.
        """
        markdown_calls = []
        mock_st = MagicMock()
        mock_st.markdown.side_effect = lambda html, **kw: markdown_calls.append(html)

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            import importlib
            import ui.components as comp
            importlib.reload(comp)
            comp.render_motivational_banner("texto con <script>alert(1)</script>")

        self.assertTrue(len(markdown_calls) > 0, "st.markdown debe ser invocado")
        rendered = markdown_calls[0]
        # El tag <script> debe estar escapado como &lt;script&gt;
        self.assertNotIn("<script>alert(1)</script>", rendered)
        self.assertIn("texto con", rendered)


if __name__ == "__main__":
    unittest.main()
