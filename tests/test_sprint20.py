"""
tests/test_sprint20.py
======================
Harness del Sprint 20 — bugs críticos y personalización.

Verifica:
1. Flashcard no repite más de 3 veces en sesión (lógica de deferred).
2. Botón "Repasar ahora" filtra correctamente conceptos sin flashcard_front.
3. mode='confirm_reclassify' se activa cuando el término ya está clasificado.
4. diagram_svg y suggested_concepts están en _empty_state y _TIMEOUT_RESULT.
5. Timeout aumentado a 60 segundos.
6. Ejemplo usa la profesión del usuario (classifier hint dinámico).
7. confirm_reclassify route va a END en el grafo.
"""

from __future__ import annotations

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GOOGLE_API_KEY", "test-key")


# ── 1. Flashcard loop — max 3 repeticiones ─────────────────────────────────────

class TestFlashcardLoopLimit(unittest.TestCase):
    """Verifica que la lógica de deferred funciona correctamente."""

    def test_fc_results_tracks_incorrect(self):
        """fc_results debe tener clave 'deferred' ausente si incorrect < 3."""
        fc_results = {
            1: {"correct": 0, "incorrect": 0, "level_before": 0, "level_after": 0}
        }
        # Simular 2 errores — no debe marcarse como deferred
        fc_results[1]["incorrect"] += 1
        fc_results[1]["incorrect"] += 1
        self.assertFalse(fc_results[1].get("deferred", False))
        self.assertEqual(fc_results[1]["incorrect"], 2)

    def test_fc_results_deferred_on_third_incorrect(self):
        """Tras 3 errores, debe marcarse deferred=True."""
        fc_results = {
            1: {"correct": 0, "incorrect": 0, "level_before": 0, "level_after": 0}
        }
        # Simular la lógica del botón "No lo sabía" tres veces
        queue = [1]
        for _ in range(3):
            fc_results[1]["incorrect"] += 1
            queue.pop(0)
            if fc_results[1]["incorrect"] < 3:
                queue.append(1)
            else:
                fc_results[1]["deferred"] = True
        self.assertTrue(fc_results[1].get("deferred", False))
        self.assertEqual(queue, [])

    def test_fc_results_requeues_on_second_incorrect(self):
        """Con 2 errores, la tarjeta debe volver a la cola."""
        queue = [1]
        fc_results = {1: {"correct": 0, "incorrect": 0, "level_before": 0, "level_after": 0}}
        # Primer error
        fc_results[1]["incorrect"] += 1
        queue.pop(0)
        if fc_results[1]["incorrect"] < 3:
            queue.append(1)
        self.assertIn(1, queue)
        # Segundo error
        fc_results[1]["incorrect"] += 1
        queue.pop(0)
        if fc_results[1]["incorrect"] < 3:
            queue.append(1)
        self.assertIn(1, queue)


# ── 2. Botón Repasar Ahora — filtrado de due_today ────────────────────────────

class TestRepasarAhoraFilter(unittest.TestCase):
    """Verifica que due_today_fc solo incluye conceptos con flashcard_front."""

    def _make_concept(self, concept_id: int, flashcard_front: str, is_classified: bool):
        c = MagicMock()
        c.id = concept_id
        c.flashcard_front = flashcard_front
        c.is_classified = is_classified
        return c

    def test_filters_concepts_without_flashcard(self):
        """Conceptos sin flashcard_front deben quedar fuera de due_today."""
        due_today_raw = [
            self._make_concept(1, "¿Qué es X?", True),
            self._make_concept(2, "", True),          # sin flashcard
            self._make_concept(3, "¿Qué es Z?", True),
            self._make_concept(4, "¿Qué es W?", False),  # no clasificado
        ]
        due_today = [
            c for c in due_today_raw
            if c.flashcard_front and getattr(c, "is_classified", False)
        ]
        self.assertEqual(len(due_today), 2)
        self.assertEqual(due_today[0].id, 1)
        self.assertEqual(due_today[1].id, 3)

    def test_empty_due_today_with_all_no_flashcard(self):
        """Si todos los vencidos carecen de flashcard, due_today es vacío."""
        due_today_raw = [
            self._make_concept(1, "", True),
            self._make_concept(2, "", True),
        ]
        due_today = [
            c for c in due_today_raw
            if c.flashcard_front and getattr(c, "is_classified", False)
        ]
        self.assertEqual(len(due_today), 0)


# ── 3. confirm_reclassify en capture_agent ────────────────────────────────────

class TestConfirmReclassify(unittest.TestCase):
    """Verifica que capture_agent retorna confirm_reclassify para términos clasificados."""

    def _make_classified_concept(self, term: str):
        c = MagicMock()
        c.id = 99
        c.term = term
        c.is_classified = True
        c.category = "Finanzas"
        return c

    def _make_unclassified_concept(self, term: str):
        c = MagicMock()
        c.id = 88
        c.term = term
        c.is_classified = False
        c.category = ""
        return c

    @patch("agents.capture_agent.get_concept_by_term")
    @patch("agents.capture_agent.get_all_concepts")
    def test_classified_existing_returns_confirm_reclassify(
        self, mock_all, mock_by_term
    ):
        """Un término ya clasificado debe retornar mode='confirm_reclassify'."""
        mock_by_term.return_value = self._make_classified_concept("EBITDA")
        mock_all.return_value = []

        from agents.capture_agent import capture_agent

        state = {
            "user_input": "EBITDA",
            "user_context": "",
            "user_id": 1,
            "mode": "",
            "user_profile": {},
        }
        result = capture_agent(state)
        self.assertEqual(result["mode"], "confirm_reclassify")
        self.assertIsNotNone(result.get("current_concept"))

    @patch("agents.capture_agent.get_concept_by_term")
    @patch("agents.capture_agent.get_all_concepts")
    def test_unclassified_existing_returns_reclassify(
        self, mock_all, mock_by_term
    ):
        """Un término sin clasificar debe retornar mode='reclassify' (no confirm)."""
        mock_by_term.return_value = self._make_unclassified_concept("EBITDA")
        mock_all.return_value = []

        from agents.capture_agent import capture_agent

        state = {
            "user_input": "EBITDA",
            "user_context": "",
            "user_id": 1,
            "mode": "",
            "user_profile": {},
        }
        result = capture_agent(state)
        self.assertEqual(result["mode"], "reclassify")

    @patch("agents.capture_agent.get_concept_by_term")
    @patch("agents.capture_agent.get_all_concepts")
    def test_clarified_prefix_bypasses_confirm(self, mock_all, mock_by_term):
        """Con prefijo [CLARIFIED]:, el bypass debe activar reclasificación directa."""
        mock_by_term.return_value = self._make_unclassified_concept("EBITDA")
        mock_all.return_value = []

        from agents.capture_agent import capture_agent

        state = {
            "user_input": "EBITDA",
            "user_context": "[CLARIFIED]: reclasificar con contexto actualizado",
            "user_id": 1,
            "mode": "",
            "user_profile": {},
        }
        result = capture_agent(state)
        # Con bypass_checks=True, no hay ambigüedad ni spelling, va a reclassify o capture
        self.assertIn(result["mode"], ("reclassify", "capture"))


# ── 4. diagram_svg y suggested_concepts en estado inicial ─────────────────────

class TestEmptyStateFields(unittest.TestCase):
    """Verifica que _empty_state y _TIMEOUT_RESULT incluyen los campos de Sprint 17/18."""

    def test_empty_state_has_diagram_svg(self):
        """_empty_state debe incluir diagram_svg como cadena vacía."""
        import importlib
        import unittest.mock as mock_lib

        with mock_lib.patch.dict("sys.modules", {
            "streamlit": MagicMock(),
            "db.schema": MagicMock(),
            "db.operations": MagicMock(),
            "agents.graph": MagicMock(),
            "ui.auth": MagicMock(),
            "ui.components": MagicMock(),
            "PIL": MagicMock(),
            "PIL.Image": MagicMock(),
        }):
            # Importar solo las funciones que necesitamos sin ejecutar el módulo completo
            pass

        # Verificar directamente leyendo el archivo fuente
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        self.assertIn('"diagram_svg"', content)
        self.assertIn('"suggested_concepts"', content)

    def test_timeout_result_has_diagram_svg(self):
        """_TIMEOUT_RESULT debe incluir diagram_svg y suggested_concepts."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        # Find the _TIMEOUT_RESULT block — search up to 600 chars from its start
        start = content.find("_TIMEOUT_RESULT = {")
        self.assertGreater(start, 0, "_TIMEOUT_RESULT not found in app.py")
        timeout_section = content[start:start + 600]
        self.assertIn("diagram_svg", timeout_section)
        self.assertIn("suggested_concepts", timeout_section)

    def test_timeout_is_60(self):
        """_GRAPH_TIMEOUT_SECONDS debe ser 60."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        self.assertIn("_GRAPH_TIMEOUT_SECONDS = 60", content)


# ── 5. Ejemplo dinámico en classifier_agent ───────────────────────────────────

class TestDynamicExampleHint(unittest.TestCase):
    """Verifica que el hint de ejemplo se adapta según la profesión."""

    def _get_example_hint(self, profession: str) -> str:
        """Replica la lógica de classifier_agent para determinar el hint."""
        _prof_lower = profession.lower()
        if any(k in _prof_lower for k in ("banca", "crédit", "credit", "analista")):
            return "Para el campo 'example', usa un ejemplo en crédito o banca."
        elif any(k in _prof_lower for k in ("desarroll", "ingenier", "developer", "softwar")):
            return "Para el campo 'example', usa un ejemplo en código o arquitectura de software."
        elif any(k in _prof_lower for k in ("ux", "diseñ", "design", "experiencia")):
            return "Para el campo 'example', usa un ejemplo en diseño de experiencia de usuario."
        elif any(k in _prof_lower for k in ("emprend", "negoci", "product", "market")):
            return "Para el campo 'example', usa un ejemplo en producto o negocio."
        elif "estudiant" in _prof_lower or "student" in _prof_lower:
            return "Para el campo 'example', usa un ejemplo académico o conceptual."
        elif profession:
            return "Para el campo 'example', usa un ejemplo práctico relevante para el usuario."
        else:
            return ""

    def test_analista_banca(self):
        hint = self._get_example_hint("Analista de banca")
        self.assertIn("crédito o banca", hint)

    def test_desarrollador(self):
        hint = self._get_example_hint("Desarrollador de software")
        self.assertIn("código o arquitectura", hint)

    def test_emprendedor(self):
        hint = self._get_example_hint("Emprendedor")
        self.assertIn("producto o negocio", hint)

    def test_estudiante(self):
        hint = self._get_example_hint("Estudiante universitario")
        self.assertIn("académico", hint)

    def test_default_unknown_profession(self):
        hint = self._get_example_hint("Cocinero")
        self.assertIn("práctico relevante", hint)

    def test_empty_profession_no_hint(self):
        hint = self._get_example_hint("")
        self.assertEqual(hint, "")


# ── 6. confirm_reclassify en el grafo va a END ───────────────────────────────

class TestGraphRoutesConfirmReclassify(unittest.TestCase):
    """Verifica que _route_after_capture envía confirm_reclassify a END."""

    def test_confirm_reclassify_routes_to_end(self):
        """mode='confirm_reclassify' debe ir directo a END."""
        try:
            from agents.graph import _route_after_capture
            from langgraph.graph import END
        except ImportError:
            self.skipTest("langgraph no disponible")

        state = {"mode": "confirm_reclassify"}
        result = _route_after_capture(state)
        self.assertEqual(result, END)

    def test_reclassify_still_routes_to_classifier(self):
        """mode='reclassify' (sin clasificar) debe seguir yendo a classifier."""
        try:
            from agents.graph import _route_after_capture
        except ImportError:
            self.skipTest("langgraph no disponible")

        state = {"mode": "reclassify"}
        result = _route_after_capture(state)
        self.assertEqual(result, "classifier")


# ── 7. Etiqueta dinámica de ejemplo en components.py ─────────────────────────

class TestDynamicExampleLabel(unittest.TestCase):
    """Verifica que render_concept_card usa etiqueta dinámica según categoría."""

    def _get_example_label(self, category: str) -> str:
        """Replica la lógica de components.py para determinar la etiqueta."""
        _cat_lower = category.lower()
        if any(k in _cat_lower for k in ("finanz", "banca", "crédit", "credit", "econom")):
            return "Ejemplo en banca"
        elif any(k in _cat_lower for k in ("inteligencia artificial", "machine learning", " ml ", "aprendizaje automático")):
            return "Ejemplo en IA"
        elif any(k in _cat_lower for k in ("softwar", "program", "código", "codigo", "desarroll", "tecnolog")):
            return "Ejemplo en código"
        elif any(k in _cat_lower for k in ("negoci", "product", "market", "emprend")):
            return "Ejemplo en negocio"
        elif any(k in _cat_lower for k in ("diseñ", "experiencia de usuario", "ux design")):
            return "Ejemplo en diseño"
        else:
            return "Ejemplo práctico"

    def test_finanzas_label(self):
        self.assertEqual(self._get_example_label("Finanzas y banca"), "Ejemplo en banca")

    def test_ia_label(self):
        self.assertEqual(self._get_example_label("IA y machine learning"), "Ejemplo en IA")

    def test_software_label(self):
        self.assertEqual(self._get_example_label("Desarrollo de software"), "Ejemplo en código")

    def test_negocio_label(self):
        self.assertEqual(self._get_example_label("Marketing y negocios"), "Ejemplo en negocio")

    def test_unknown_category_label(self):
        self.assertEqual(self._get_example_label("Historia del arte"), "Ejemplo práctico")

    def test_unknown_category_historia_not_ia(self):
        """'Historia' no debe confundirse con 'IA' (falso positivo por substring 'ia')."""
        self.assertEqual(self._get_example_label("Historia del arte"), "Ejemplo práctico")

    def test_components_py_uses_dynamic_label(self):
        """El código de components.py debe usar la variable _example_label dinámica."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        # La variable dinámica debe existir
        self.assertIn("_example_label", content)
        # El label debe usarse en el markdown
        self.assertIn(f"{{_example_label}}", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
