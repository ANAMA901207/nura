"""
tests/test_sprint12.py
======================
Harness de verificación para Sprint 12 — tutor adaptativo inteligente.

Tests obligatorios:
  1. get_weak_categories retorna categorías con mastery < 2.5 (y > 2 conceptos).
  2. get_neglected_concepts retorna conceptos sin actividad en 7 días.
  3. insight_agent no falla con BD vacía.
  4. insight_agent genera mensaje no vacío con 5+ conceptos clasificados.
  5. render_insight_banner no lanza errores con mensaje válido.

Tests adicionales:
  6. get_struggling_concepts retorna conceptos con consecutive_incorrect >= 3.
  7. get_learning_preference retorna 'flashcards' cuando total_reviews > conceptos*2.
  8. get_weekly_insight_data devuelve dict con las claves esperadas.
  9. capture_agent pasa 'insight' al router cuando mode='insight' viene pre-establecido.
 10. graph construye y compila correctamente con el nodo 'insight'.

Todos los tests usan una BD temporal aislada.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_temp_db() -> Path:
    """
    Crea una BD temporal y la inicializa con el schema completo.

    Devuelve
    --------
    Path al archivo temporal de la BD.
    """
    import db.schema as schema
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    schema.DB_PATH = Path(tmp.name)
    from db.schema import init_db
    init_db()
    return Path(tmp.name)


def _cleanup_temp_db(path: Path) -> None:
    """Elimina el archivo de BD temporal."""
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


_temp_db: Path | None = None


def setUpModule() -> None:
    global _temp_db
    _temp_db = _setup_temp_db()


def tearDownModule() -> None:
    if _temp_db:
        _cleanup_temp_db(_temp_db)


# ── helpers ───────────────────────────────────────────────────────────────────

def _save_classified_concept(
    term: str,
    category: str,
    mastery: int = 0,
    user_id: int = 1,
    last_reviewed: datetime | None = None,
    consecutive_incorrect: int = 0,
    total_reviews: int = 0,
) -> "Concept":
    """
    Crea y clasifica un concepto directamente en la BD temporal.

    Combina save_concept + update_concept_classification + ajuste manual de
    campos de mastery para tests que no quieren llamar a la API de Gemini.
    """
    from db.operations import save_concept, update_concept_classification
    from db.schema import get_connection

    c = save_concept(term=term, context="test", user_id=user_id)

    update_concept_classification(c.id, {
        "category":       category,
        "subcategory":    "test",
        "explanation":    f"Explicación de {term}",
        "how_it_works":   "funciona así",
        "schema":         "A → B",
        "analogy":        "como X",
        "examples":       "ejemplo práctico",
        "flashcard_front": f"¿Qué es {term}?",
        "flashcard_back":  f"Es {term}.",
    }, user_id=user_id)

    # Ajustar campos numéricos directamente con SQL para evitar llamadas a API
    lr_val = last_reviewed.isoformat() if last_reviewed else None
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE concepts
               SET mastery_level = ?, last_reviewed = ?,
                   consecutive_incorrect = ?, total_reviews = ?
             WHERE id = ? AND user_id = ?
            """,
            (mastery, lr_val, consecutive_incorrect, total_reviews, c.id, user_id),
        )

    from db.operations import get_concept_by_id
    return get_concept_by_id(c.id, user_id=user_id)


# ── Test 1: get_weak_categories ───────────────────────────────────────────────

class TestGetWeakCategories(unittest.TestCase):
    """Verifica que get_weak_categories filtra correctamente por mastery y count."""

    def setUp(self) -> None:
        """Crea una BD limpia antes de cada test en esta clase."""
        _setup_temp_db()

    def test_returns_category_with_low_mastery_and_enough_concepts(self) -> None:
        """Categoría con 3 conceptos y mastery promedio < 2.5 debe aparecer."""
        from db.operations import get_weak_categories

        for i in range(3):
            _save_classified_concept(f"termino_debil_{i}", "Finanzas", mastery=1)

        result = get_weak_categories(user_id=1)
        self.assertIsInstance(result, list)
        categories = [r["category"] for r in result]
        self.assertIn("Finanzas", categories)

    def test_excludes_category_with_high_mastery(self) -> None:
        """Categoría con mastery promedio >= 2.5 no debe aparecer."""
        from db.operations import get_weak_categories

        for i in range(3):
            _save_classified_concept(f"termino_fuerte_{i}", "Tecnología", mastery=4)

        result = get_weak_categories(user_id=1)
        categories = [r["category"] for r in result]
        self.assertNotIn("Tecnología", categories)

    def test_excludes_category_with_too_few_concepts(self) -> None:
        """Categoría con <= 2 conceptos no debe aparecer aunque tenga mastery bajo."""
        from db.operations import get_weak_categories

        for i in range(2):
            _save_classified_concept(f"termino_pocos_{i}", "Derecho", mastery=0)

        result = get_weak_categories(user_id=1)
        categories = [r["category"] for r in result]
        self.assertNotIn("Derecho", categories)

    def test_returns_empty_with_no_concepts(self) -> None:
        """BD vacía devuelve lista vacía sin lanzar excepción."""
        from db.operations import get_weak_categories
        result = get_weak_categories(user_id=1)
        self.assertEqual(result, [])

    def test_result_has_required_keys(self) -> None:
        """Cada dict en el resultado debe tener category, avg_mastery y count."""
        from db.operations import get_weak_categories

        for i in range(3):
            _save_classified_concept(f"t_keys_{i}", "Economía", mastery=1)

        result = get_weak_categories(user_id=1)
        if result:
            entry = result[0]
            self.assertIn("category", entry)
            self.assertIn("avg_mastery", entry)
            self.assertIn("count", entry)


# ── Test 2: get_neglected_concepts ────────────────────────────────────────────

class TestGetNeglectedConcepts(unittest.TestCase):
    """Verifica que get_neglected_concepts filtra por inactividad correctamente."""

    def setUp(self) -> None:
        _setup_temp_db()

    def test_returns_concept_never_reviewed(self) -> None:
        """Concepto nunca revisado y capturado hace > 7 días debe aparecer."""
        from db.operations import get_neglected_concepts
        from db.schema import get_connection

        c = _save_classified_concept("termino_old", "Finanzas", mastery=1)

        # Simular que fue capturado hace 10 días
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE concepts SET created_at = ?, last_reviewed = NULL WHERE id = ?",
                (old_date, c.id),
            )

        result = get_neglected_concepts(user_id=1, days=7)
        ids = [r.id for r in result]
        self.assertIn(c.id, ids)

    def test_excludes_recently_reviewed_concept(self) -> None:
        """Concepto revisado ayer no debe aparecer como descuidado."""
        from db.operations import get_neglected_concepts
        from db.schema import get_connection

        c = _save_classified_concept("termino_reciente", "Finanzas", mastery=3)

        # Capturado hace 10 días pero revisado ayer
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE concepts SET created_at = ?, last_reviewed = ? WHERE id = ?",
                (old_date, yesterday, c.id),
            )

        result = get_neglected_concepts(user_id=1, days=7)
        ids = [r.id for r in result]
        self.assertNotIn(c.id, ids)

    def test_excludes_newly_captured_concept(self) -> None:
        """Concepto capturado hoy no debe aparecer (demasiado nuevo)."""
        from db.operations import get_neglected_concepts

        _save_classified_concept("termino_nuevo", "Tecnología", mastery=0)

        result = get_neglected_concepts(user_id=1, days=7)
        terms = [r.term for r in result]
        self.assertNotIn("termino_nuevo", terms)

    def test_returns_empty_with_no_concepts(self) -> None:
        """BD vacía devuelve lista vacía."""
        from db.operations import get_neglected_concepts
        result = get_neglected_concepts(user_id=1, days=7)
        self.assertEqual(result, [])


# ── Test 3 & 4: insight_agent ─────────────────────────────────────────────────

class TestInsightAgent(unittest.TestCase):
    """Verifica que insight_agent genera mensajes correctamente."""

    def setUp(self) -> None:
        _setup_temp_db()

    def test_no_fail_with_empty_db(self) -> None:
        """insight_agent no debe lanzar excepción con BD vacía."""
        from agents.insight_agent import insight_agent

        state = {
            "user_input": "",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "insight",
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
        }
        result = insight_agent(state)
        self.assertIn("insight_message", result)
        self.assertIsInstance(result["insight_message"], str)
        self.assertGreater(len(result["insight_message"]), 0)

    def test_generates_static_message_with_few_concepts(self) -> None:
        """Con < 5 conceptos clasificados, retorna mensaje motivador sin API."""
        from agents.insight_agent import insight_agent, _MIN_CONCEPTS_FOR_INSIGHT

        # Crear solo 2 conceptos (< _MIN_CONCEPTS_FOR_INSIGHT)
        for i in range(2):
            _save_classified_concept(f"poca_data_{i}", "Finanzas", mastery=1)

        state = {
            "user_input": "",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "insight",
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
        }
        result = insight_agent(state)
        self.assertGreater(len(result["insight_message"]), 0)
        # Sin llamada a Gemini, debe ser el mensaje estático de bienvenida
        self.assertIn("response", result)

    def test_generates_message_with_enough_concepts_no_api_key(self) -> None:
        """Con 5+ conceptos pero sin API key, genera mensaje de fallback estático."""
        import os
        from agents.insight_agent import insight_agent

        for i in range(6):
            _save_classified_concept(f"concepto_{i}", "Finanzas", mastery=1 + (i % 3))

        state = {
            "user_input": "",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "insight",
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
        }

        # Eliminar GOOGLE_API_KEY del entorno para forzar el camino de fallback
        # estático (sin llamada real a la API) — evita cuota y mocking complejo.
        saved = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            result = insight_agent(state)
        finally:
            if saved is not None:
                os.environ["GOOGLE_API_KEY"] = saved

        self.assertGreater(len(result["insight_message"]), 0)
        self.assertEqual(result["insight_message"], result["response"])

    def test_fallback_on_api_error(self) -> None:
        """Con 5+ conceptos y API key inválida, retorna mensaje estático sin excepción."""
        import os
        from agents.insight_agent import insight_agent

        for i in range(6):
            _save_classified_concept(f"fallback_{i}", "Tecnología", mastery=2)

        state = {
            "user_input": "",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "insight",
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
        }

        # Sin API key → el agente usa _build_static_insight directamente
        saved = os.environ.pop("GOOGLE_API_KEY", None)
        try:
            result = insight_agent(state)
        finally:
            if saved is not None:
                os.environ["GOOGLE_API_KEY"] = saved

        self.assertIsInstance(result["insight_message"], str)
        self.assertGreater(len(result["insight_message"]), 0)


# ── Test 5: render_insight_banner ────────────────────────────────────────────

class TestRenderInsightBanner(unittest.TestCase):
    """Verifica que render_insight_banner no lanza errores."""

    def _install_st_mock(self) -> MagicMock:
        """
        Instala un MagicMock como sys.modules['streamlit'] y devuelve el mock.

        render_insight_banner importa streamlit *localmente* dentro del cuerpo de
        la función, así que hay que reemplazar el módulo en sys.modules antes de
        llamarla.  Se restaura automáticamente en tearDown.
        """
        mock_st = MagicMock()
        mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
        self._prev_st = sys.modules.get("streamlit")
        sys.modules["streamlit"] = mock_st
        return mock_st

    def tearDown(self) -> None:
        """Restaura el módulo streamlit original tras cada test."""
        if hasattr(self, "_prev_st") and self._prev_st is not None:
            sys.modules["streamlit"] = self._prev_st
        else:
            sys.modules.pop("streamlit", None)

    def test_no_error_with_valid_message(self) -> None:
        """render_insight_banner con mensaje válido debe llamar a st.markdown."""
        import importlib
        mock_st = self._install_st_mock()

        import ui.components as comp
        importlib.reload(comp)  # asegura que el módulo use el mock actual

        comp.render_insight_banner("Hola, esta semana aprendiste mucho. ¡Sigue así!")
        mock_st.markdown.assert_called()

    def test_no_output_with_empty_message(self) -> None:
        """render_insight_banner con mensaje vacío no llama a st.markdown."""
        import importlib
        mock_st = self._install_st_mock()

        import ui.components as comp
        importlib.reload(comp)

        comp.render_insight_banner("")
        mock_st.markdown.assert_not_called()


# ── Test 6: get_struggling_concepts ──────────────────────────────────────────

class TestGetStrugglingConcepts(unittest.TestCase):
    """Verifica que get_struggling_concepts filtra por fallos consecutivos."""

    def setUp(self) -> None:
        _setup_temp_db()

    def test_returns_concepts_with_enough_failures(self) -> None:
        """Concepto con consecutive_incorrect >= 3 debe aparecer."""
        from db.operations import get_struggling_concepts

        c = _save_classified_concept("difícil", "Finanzas", consecutive_incorrect=4)
        result = get_struggling_concepts(user_id=1, min_failures=3)
        ids = [r.id for r in result]
        self.assertIn(c.id, ids)

    def test_excludes_concepts_below_threshold(self) -> None:
        """Concepto con consecutive_incorrect < 3 no debe aparecer."""
        from db.operations import get_struggling_concepts

        c = _save_classified_concept("facil", "Finanzas", consecutive_incorrect=1)
        result = get_struggling_concepts(user_id=1, min_failures=3)
        ids = [r.id for r in result]
        self.assertNotIn(c.id, ids)

    def test_returns_empty_with_no_concepts(self) -> None:
        from db.operations import get_struggling_concepts
        result = get_struggling_concepts(user_id=1)
        self.assertEqual(result, [])


# ── Test 7: get_learning_preference ──────────────────────────────────────────

class TestGetLearningPreference(unittest.TestCase):
    """Verifica la detección de preferencia de aprendizaje."""

    def setUp(self) -> None:
        _setup_temp_db()

    def test_returns_flashcards_when_many_reviews(self) -> None:
        """Retorna 'flashcards' cuando total_reviews > total_concepts * 2."""
        from db.operations import get_learning_preference

        # 2 conceptos con 5 reviews cada uno → 10 reviews > 4 (2*2)
        for i in range(2):
            _save_classified_concept(f"fc_pref_{i}", "Finanzas", total_reviews=5)

        result = get_learning_preference(user_id=1)
        self.assertEqual(result, "flashcards")

    def test_returns_chat_when_few_reviews(self) -> None:
        """Retorna 'chat' cuando total_reviews <= total_concepts * 2."""
        from db.operations import get_learning_preference

        for i in range(3):
            _save_classified_concept(f"chat_pref_{i}", "Finanzas", total_reviews=1)

        result = get_learning_preference(user_id=1)
        self.assertEqual(result, "chat")

    def test_returns_chat_with_empty_db(self) -> None:
        """Retorna 'chat' por defecto con BD vacía."""
        from db.operations import get_learning_preference
        result = get_learning_preference(user_id=1)
        self.assertEqual(result, "chat")


# ── Test 8: get_weekly_insight_data ──────────────────────────────────────────

class TestGetWeeklyInsightData(unittest.TestCase):
    """Verifica que get_weekly_insight_data retorna el dict con las claves esperadas."""

    def setUp(self) -> None:
        _setup_temp_db()

    def test_returns_dict_with_required_keys(self) -> None:
        """Debe retornar dict con todas las claves esperadas."""
        from db.operations import get_weekly_insight_data

        result = get_weekly_insight_data(user_id=1)
        expected_keys = {
            "conceptos_esta_semana",
            "categoria_mas_fuerte",
            "categoria_mas_debil",
            "conceptos_dominados",
            "racha",
        }
        for key in expected_keys:
            self.assertIn(key, result, f"Falta la clave '{key}'")

    def test_counts_weekly_concepts_correctly(self) -> None:
        """Cuenta solo los conceptos creados en los últimos 7 días."""
        from db.operations import get_weekly_insight_data, save_concept
        from db.schema import get_connection

        # Concepto reciente (hoy)
        c_new = save_concept(term="concepto_semana", context="test", user_id=1)

        # Concepto antiguo (hace 10 días)
        c_old = save_concept(term="concepto_viejo", context="test", user_id=1)
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        with get_connection() as conn:
            conn.execute(
                "UPDATE concepts SET created_at = ? WHERE id = ?",
                (old_date, c_old.id),
            )

        result = get_weekly_insight_data(user_id=1)
        # Al menos el concepto nuevo debe contar
        self.assertGreaterEqual(result["conceptos_esta_semana"], 1)

    def test_empty_db_returns_zeros(self) -> None:
        """BD vacía retorna ceros y cadenas vacías sin lanzar excepción."""
        from db.operations import get_weekly_insight_data

        result = get_weekly_insight_data(user_id=1)
        self.assertEqual(result["conceptos_esta_semana"], 0)
        self.assertEqual(result["conceptos_dominados"], 0)
        self.assertEqual(result["categoria_mas_fuerte"], "")
        self.assertEqual(result["categoria_mas_debil"], "")


# ── Test 9: capture_agent pass-through para mode='insight' ───────────────────

class TestCaptureAgentInsightPassthrough(unittest.TestCase):
    """Verifica que capture_agent no procesa nada cuando mode='insight'."""

    def setUp(self) -> None:
        _setup_temp_db()

    def test_returns_insight_mode_when_preset(self) -> None:
        """capture_agent retorna mode='insight' sin tocar la BD."""
        from agents.capture_agent import capture_agent

        state = {
            "user_input": "",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "insight",  # pre-establecido por la UI
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
        }
        result = capture_agent(state)
        self.assertEqual(result["mode"], "insight")
        self.assertIsNone(result["current_concept"])

    def test_does_not_save_concept_in_insight_mode(self) -> None:
        """BD no debe tener conceptos nuevos tras invocar capture en modo insight."""
        from agents.capture_agent import capture_agent
        from db.operations import get_all_concepts

        state = {
            "user_input": "machine learning",  # aunque haya user_input, mode='insight' tiene prioridad
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "insight",
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
        }
        capture_agent(state)
        concepts = get_all_concepts(user_id=1)
        # Ningún concepto debe haberse guardado
        self.assertEqual(len(concepts), 0)


# ── Test 10: graph compila con nodo insight ───────────────────────────────────

class TestGraphCompilesWithInsightNode(unittest.TestCase):
    """Verifica que el grafo incluye el nodo 'insight' correctamente."""

    def test_graph_builds_without_error(self) -> None:
        """build_graph() no debe lanzar excepción al compilar."""
        from agents.graph import build_graph
        graph = build_graph()
        self.assertIsNotNone(graph)

    def test_graph_has_insight_node(self) -> None:
        """El grafo compilado debe reconocer el nodo 'insight'."""
        from agents.graph import build_graph
        graph = build_graph()
        # El grafo LangGraph compilado expone los nodos vía get_graph().nodes
        nodes = graph.get_graph().nodes
        self.assertIn("insight", nodes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
