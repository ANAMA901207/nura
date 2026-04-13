"""
tests/test_sprint18.py
======================
Harness del Sprint 18 — tutor detecta conceptos nuevos y sugiere agregarlos.

Verifica:
1. detect_new_concepts retorna lista de strings.
2. Términos ya existentes se filtran correctamente (case-insensitive).
3. Retorna máximo 5 conceptos aunque Gemini devuelva más.
4. Fallo de API retorna lista vacía sin excepción.
5. Lista vacía no activa el banner de sugerencias en la UI.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestDetectNewConceptsReturnType(unittest.TestCase):
    """(1) detect_new_concepts retorna lista de strings."""

    def test_returns_list(self):
        """El tipo de retorno es siempre list."""
        mock_data = {"concepts": ["LangChain", "vectores", "embedding"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts("texto largo de prueba para el detector", [], 1)
        self.assertIsInstance(result, list)

    def test_elements_are_strings(self):
        """Cada elemento de la lista es un string."""
        mock_data = {"concepts": ["RAG", "LLM", "tokenización"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts("texto de demostración extenso con contenido", [], 1)
        for item in result:
            self.assertIsInstance(item, str)

    def test_returns_empty_for_short_text(self):
        """No llama a Gemini y retorna lista vacía con texto muy corto."""
        with patch("tools.concept_detector_tool._call_gemini_concepts") as mock_llm:
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts("corto", [], 1)
        self.assertEqual(result, [])
        mock_llm.assert_not_called()

    def test_returns_empty_for_empty_string(self):
        """Retorna lista vacía con texto vacío sin llamar a Gemini."""
        with patch("tools.concept_detector_tool._call_gemini_concepts") as mock_llm:
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts("", [], 1)
        self.assertEqual(result, [])
        mock_llm.assert_not_called()


class TestExistingTermsFiltered(unittest.TestCase):
    """(2) Términos ya existentes se filtran correctamente (case-insensitive)."""

    def test_filters_exact_match(self):
        """Un término idéntico al existente no aparece en el resultado."""
        mock_data = {"concepts": ["LangChain", "vectores", "embedding"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso",
                existing_terms=["LangChain"],
                user_id=1,
            )
        self.assertNotIn("LangChain", result)
        self.assertIn("vectores", result)

    def test_filters_case_insensitive(self):
        """La comparación ignora mayúsculas/minúsculas."""
        mock_data = {"concepts": ["langchain", "BERT", "embeddings"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                existing_terms=["LangChain", "bert"],
                user_id=1,
            )
        self.assertNotIn("langchain", result)
        self.assertNotIn("BERT", result)
        self.assertIn("embeddings", result)

    def test_no_filter_when_existing_is_empty(self):
        """Con lista vacía de existentes, devuelve todos los detectados."""
        mock_data = {"concepts": ["RAG", "LLM", "pipeline"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                existing_terms=[],
                user_id=1,
            )
        self.assertEqual(len(result), 3)

    def test_all_filtered_returns_empty(self):
        """Si todos los conceptos detectados ya existen, retorna lista vacía."""
        mock_data = {"concepts": ["RAG", "LLM"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                existing_terms=["rag", "llm"],
                user_id=1,
            )
        self.assertEqual(result, [])


class TestMaxFiveConcepts(unittest.TestCase):
    """(3) Retorna máximo 5 conceptos aunque Gemini devuelva más."""

    def test_caps_at_five(self):
        """Con 10 conceptos de Gemini, solo devuelve 5."""
        mock_data = {
            "concepts": [
                "RAG", "LLM", "vectores", "embedding", "tokenización",
                "transformer", "BERT", "GPT", "fine-tuning", "prompt"
            ]
        }
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                existing_terms=[],
                user_id=1,
            )
        self.assertLessEqual(len(result), 5)

    def test_exactly_five_when_six_available(self):
        """Con 6 conceptos válidos de Gemini, devuelve exactamente 5."""
        mock_data = {"concepts": ["A", "B", "C", "D", "E", "F"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                existing_terms=[],
                user_id=1,
            )
        self.assertEqual(len(result), 5)

    def test_fewer_than_five_when_fewer_available(self):
        """Con 3 conceptos válidos, devuelve los 3 sin relleno."""
        mock_data = {"concepts": ["RAG", "LLM", "BERT"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                existing_terms=[],
                user_id=1,
            )
        self.assertEqual(len(result), 3)


class TestApiFailureSafe(unittest.TestCase):
    """(4) Fallo de API retorna lista vacía sin excepción."""

    def test_network_error_returns_empty(self):
        """Retorna [] cuando _call_gemini_concepts lanza Exception."""
        with patch(
            "tools.concept_detector_tool._call_gemini_concepts",
            side_effect=Exception("network error"),
        ):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                [],
                1,
            )
        self.assertEqual(result, [])

    def test_json_error_returns_empty(self):
        """Retorna [] cuando el JSON es inválido."""
        with patch(
            "tools.concept_detector_tool._call_gemini_concepts",
            side_effect=ValueError("invalid json"),
        ):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                [],
                1,
            )
        self.assertEqual(result, [])

    def test_no_exception_propagated(self):
        """No se propaga ninguna excepción al caller."""
        with patch(
            "tools.concept_detector_tool._call_gemini_concepts",
            side_effect=RuntimeError("crash"),
        ):
            from tools.concept_detector_tool import detect_new_concepts
            try:
                detect_new_concepts("texto largo para que no sea corto y pase el guard", [], 1)
            except Exception as exc:
                self.fail(f"detect_new_concepts propagó excepción: {exc}")

    def test_permission_error_returns_empty(self):
        """Retorna [] ante errores de autenticación (403)."""
        with patch(
            "tools.concept_detector_tool._call_gemini_concepts",
            side_effect=PermissionError("403 Forbidden"),
        ):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso", [], 1
            )
        self.assertEqual(result, [])


class TestBannerNotShownForEmptyList(unittest.TestCase):
    """(5) Lista vacía no activa el banner — verificado a través del state."""

    def test_tutor_agent_suggested_concepts_key_present(self):
        """tutor_agent siempre incluye 'suggested_concepts' en el resultado."""
        with patch("agents.tutor_agent._call_gemini", return_value="Respuesta del tutor"), \
             patch("agents.tutor_agent.get_all_concepts", return_value=[]), \
             patch("agents.tutor_agent.web_search", return_value={"results": []}), \
             patch("os.environ.get", return_value="fake-key"), \
             patch("agents.tutor_agent.ChatGoogleGenerativeAI"), \
             patch("tools.concept_detector_tool.detect_new_concepts", return_value=[]):
            from agents.tutor_agent import tutor_agent
            state = {
                "user_input":   "¿Qué es LangChain?",
                "user_context": "",
                "mode":         "question",
                "user_id":      1,
                "user_profile": {},
                "sources":      [],
                "diagram_svg":  "",
                "suggested_concepts": [],
            }
            result = tutor_agent(state)

        self.assertIn("suggested_concepts", result)
        self.assertIsInstance(result["suggested_concepts"], list)

    def test_empty_suggested_concepts_for_failed_detection(self):
        """Si detect_new_concepts falla, suggested_concepts es [] en el resultado."""
        with patch("agents.tutor_agent._call_gemini", return_value="Respuesta del tutor"), \
             patch("agents.tutor_agent.get_all_concepts", return_value=[]), \
             patch("agents.tutor_agent.web_search", return_value={"results": []}), \
             patch("os.environ.get", return_value="fake-key"), \
             patch("agents.tutor_agent.ChatGoogleGenerativeAI"), \
             patch("tools.concept_detector_tool.detect_new_concepts",
                   side_effect=Exception("fallo detector")):
            from agents.tutor_agent import tutor_agent
            state = {
                "user_input":   "¿Cómo funciona RAG?",
                "user_context": "",
                "mode":         "question",
                "user_id":      1,
                "user_profile": {},
                "sources":      [],
                "diagram_svg":  "",
                "suggested_concepts": [],
            }
            result = tutor_agent(state)

        self.assertEqual(result["suggested_concepts"], [])

    def test_suggested_concepts_with_real_detection(self):
        """Si detect_new_concepts devuelve términos, se incluyen en el resultado."""
        with patch("agents.tutor_agent._call_gemini", return_value="Respuesta del tutor"), \
             patch("agents.tutor_agent.get_all_concepts", return_value=[]), \
             patch("agents.tutor_agent.web_search", return_value={"results": []}), \
             patch("os.environ.get", return_value="fake-key"), \
             patch("agents.tutor_agent.ChatGoogleGenerativeAI"), \
             patch("tools.concept_detector_tool.detect_new_concepts",
                   return_value=["RAG", "embedding"]):
            from agents.tutor_agent import tutor_agent
            state = {
                "user_input":   "¿Qué es RAG?",
                "user_context": "",
                "mode":         "question",
                "user_id":      1,
                "user_profile": {},
                "sources":      [],
                "diagram_svg":  "",
                "suggested_concepts": [],
            }
            result = tutor_agent(state)

        self.assertIn("RAG", result["suggested_concepts"])
        self.assertIn("embedding", result["suggested_concepts"])


class TestWordCountFilter(unittest.TestCase):
    """Tests de la regla de máximo 4 palabras por concepto."""

    def test_five_word_concept_excluded(self):
        """Conceptos con más de 4 palabras se excluyen del resultado."""
        mock_data = {
            "concepts": [
                "RAG",
                "esto tiene cinco palabras ahora",  # debe excluirse
                "embedding",
            ]
        }
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                [],
                1,
            )
        self.assertNotIn("esto tiene cinco palabras ahora", result)
        self.assertIn("RAG", result)
        self.assertIn("embedding", result)

    def test_four_word_concept_included(self):
        """Conceptos con exactamente 4 palabras se incluyen."""
        mock_data = {"concepts": ["machine learning supervisado avanzado"]}
        with patch("tools.concept_detector_tool._call_gemini_concepts", return_value=mock_data):
            from tools.concept_detector_tool import detect_new_concepts
            result = detect_new_concepts(
                "texto largo de prueba suficientemente extenso para el test",
                [],
                1,
            )
        self.assertIn("machine learning supervisado avanzado", result)


if __name__ == "__main__":
    unittest.main()
