"""
tests/test_sprint19.py
======================
Harness del Sprint 19 — tools formales LangGraph.

Verifica:
1. Cada tool registrada es invocable con la interfaz correcta.
2. ToolNode se instancia sin errores con NURA_TOOLS.
3. Los tools de BD retornan JSON válido.
4. bind_tools() no lanza errores en los agentes.
5. Las interfaces públicas originales siguen intactas (regresión cero).
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestToolsAreRegistered(unittest.TestCase):
    """(1) Cada tool formal existe y tiene los atributos esperados."""

    def test_save_concept_tool_has_name(self):
        """save_concept_tool tiene nombre y descripción."""
        from tools.db_tools import save_concept_tool
        self.assertEqual(save_concept_tool.name, "save_concept_tool")
        self.assertTrue(len(save_concept_tool.description) > 0)

    def test_get_concepts_tool_has_name(self):
        from tools.db_tools import get_concepts_tool
        self.assertEqual(get_concepts_tool.name, "get_concepts_tool")

    def test_update_mastery_tool_has_name(self):
        from tools.db_tools import update_mastery_tool
        self.assertEqual(update_mastery_tool.name, "update_mastery_tool")

    def test_classify_concept_tool_has_name(self):
        from tools.classifier_tool import classify_concept_tool
        self.assertEqual(classify_concept_tool.name, "classify_concept_tool")
        self.assertTrue(len(classify_concept_tool.description) > 0)

    def test_find_connections_tool_has_name(self):
        from tools.connector_tool import find_connections_tool
        self.assertEqual(find_connections_tool.name, "find_connections_tool")

    def test_search_web_tool_has_name(self):
        from tools.search_tool import search_web_tool
        self.assertEqual(search_web_tool.name, "search_web_tool")

    def test_nura_tools_list_has_six_tools(self):
        """NURA_TOOLS contiene exactamente los 6 tools del sprint."""
        from tools.db_tools import NURA_TOOLS
        self.assertEqual(len(NURA_TOOLS), 6)

    def test_nura_tools_are_all_tool_instances(self):
        """Todos los elementos de NURA_TOOLS son instancias de BaseTool."""
        from tools.db_tools import NURA_TOOLS
        from langchain_core.tools import BaseTool
        for t in NURA_TOOLS:
            self.assertIsInstance(t, BaseTool, f"{t} no es BaseTool")


class TestToolNodeInstantiation(unittest.TestCase):
    """(2) ToolNode se instancia correctamente con NURA_TOOLS."""

    def test_tool_node_creates_without_error(self):
        """ToolNode(NURA_TOOLS) no lanza ninguna excepción."""
        from langgraph.prebuilt import ToolNode
        from tools.db_tools import NURA_TOOLS
        try:
            node = ToolNode(NURA_TOOLS)
        except Exception as exc:
            self.fail(f"ToolNode(NURA_TOOLS) lanzó excepción: {exc}")
        self.assertIsNotNone(node)

    def test_tool_node_registered_in_graph(self):
        """El nodo 'tools' está registrado en el grafo compilado."""
        from agents.graph import build_graph
        graph = build_graph()
        # Los nodos compilados están en graph.nodes
        self.assertIn("tools", graph.nodes)


class TestDbToolsReturnJson(unittest.TestCase):
    """(3) Los tools de BD retornan strings JSON válidos."""

    def test_save_concept_tool_returns_json_on_success(self):
        """save_concept_tool retorna JSON con 'id' y 'term' al guardar."""
        mock_concept = MagicMock()
        mock_concept.id   = 42
        mock_concept.term = "LangChain"
        # save_concept is a module-level import in db_tools → patchable there
        with patch("tools.db_tools.save_concept", return_value=mock_concept):
            from tools.db_tools import save_concept_tool
            result = save_concept_tool.invoke({"term": "LangChain", "user_id": 1})
        data = json.loads(result)
        self.assertEqual(data["id"], 42)
        self.assertEqual(data["term"], "LangChain")
        self.assertEqual(data["status"], "saved")

    def test_save_concept_tool_returns_error_json_on_failure(self):
        """save_concept_tool retorna JSON con 'error' al fallar."""
        with patch("tools.db_tools.save_concept", side_effect=ValueError("duplicado")):
            from tools.db_tools import save_concept_tool
            result = save_concept_tool.invoke({"term": "LangChain", "user_id": 1})
        data = json.loads(result)
        self.assertIn("error", data)

    def test_get_concepts_tool_returns_json_list(self):
        """get_concepts_tool retorna JSON array."""
        mock_c = MagicMock()
        mock_c.id, mock_c.term, mock_c.category, mock_c.mastery_level = 1, "RAG", "IA", 2
        with patch("tools.db_tools.get_all_concepts", return_value=[mock_c]):
            from tools.db_tools import get_concepts_tool
            result = get_concepts_tool.invoke({"user_id": 1})
        data = json.loads(result)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["term"], "RAG")

    def test_get_concepts_tool_returns_empty_list_when_no_concepts(self):
        """get_concepts_tool retorna [] cuando no hay conceptos."""
        with patch("tools.db_tools.get_all_concepts", return_value=[]):
            from tools.db_tools import get_concepts_tool
            result = get_concepts_tool.invoke({"user_id": 1})
        self.assertEqual(json.loads(result), [])

    def test_update_mastery_tool_returns_json(self):
        """update_mastery_tool retorna JSON con mastery_level actualizado."""
        mock_c = MagicMock()
        mock_c.id, mock_c.term, mock_c.mastery_level = 5, "BERT", 3
        with patch("tools.db_tools.record_flashcard_result", return_value=mock_c):
            from tools.db_tools import update_mastery_tool
            result = update_mastery_tool.invoke({"concept_id": 5, "correct": True, "user_id": 1})
        data = json.loads(result)
        self.assertEqual(data["mastery_level"], 3)
        self.assertEqual(data["status"], "updated")


class TestClassifierToolFormal(unittest.TestCase):
    """classify_concept_tool retorna JSON de clasificación."""

    def test_classify_concept_tool_returns_json_on_success(self):
        mock_result = {"category": "IA", "subcategory": "NLP", "explanation": "..."}
        with patch("tools.classifier_tool.classify_concept", return_value=mock_result):
            from tools.classifier_tool import classify_concept_tool
            result = classify_concept_tool.invoke({"term": "BERT"})
        data = json.loads(result)
        self.assertEqual(data["category"], "IA")

    def test_classify_concept_tool_returns_error_json_on_failure(self):
        from tools.classifier_tool import ClassificationError
        with patch("tools.classifier_tool.classify_concept",
                   side_effect=ClassificationError("API falla")):
            from tools.classifier_tool import classify_concept_tool
            result = classify_concept_tool.invoke({"term": "BERT"})
        data = json.loads(result)
        self.assertIn("error", data)


class TestConnectorToolFormal(unittest.TestCase):
    """find_connections_tool retorna JSON de conexiones."""

    def test_find_connections_tool_returns_json_list(self):
        mock_concept = MagicMock()
        mock_concept.id = 1
        mock_connections = [{"concept_id": 2, "relationship": "es parte de"}]
        # get_concept_by_id and get_all_concepts are module-level imports in connector_tool
        with patch("tools.connector_tool.get_concept_by_id", return_value=mock_concept), \
             patch("tools.connector_tool.get_all_concepts", return_value=[mock_concept]), \
             patch("tools.connector_tool.find_connections", return_value=mock_connections):
            from tools.connector_tool import find_connections_tool
            result = find_connections_tool.invoke({"concept_id": 1, "user_id": 1})
        data = json.loads(result)
        self.assertIsInstance(data, list)

    def test_find_connections_tool_returns_error_on_failure(self):
        # get_concept_by_id is a module-level import in connector_tool
        with patch("tools.connector_tool.get_concept_by_id",
                   side_effect=Exception("no encontrado")):
            from tools.connector_tool import find_connections_tool
            result = find_connections_tool.invoke({"concept_id": 99, "user_id": 1})
        data = json.loads(result)
        self.assertIn("error", data)


class TestSearchToolFormal(unittest.TestCase):
    """search_web_tool retorna JSON de resultados de búsqueda."""

    def test_search_web_tool_returns_json(self):
        mock_result = {"results": [{"title": "Test", "url": "http://x.com", "snippet": "..."}]}
        with patch("tools.search_tool.web_search", return_value=mock_result):
            from tools.search_tool import search_web_tool
            result = search_web_tool.invoke({"query": "LangChain 2026"})
        data = json.loads(result)
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)

    def test_search_web_tool_returns_empty_on_failure(self):
        mock_result = {"results": [], "error": "timeout"}
        with patch("tools.search_tool.web_search", return_value=mock_result):
            from tools.search_tool import search_web_tool
            result = search_web_tool.invoke({"query": "algo"})
        data = json.loads(result)
        self.assertEqual(data["results"], [])


class TestBindToolsInAgents(unittest.TestCase):
    """(4) bind_tools() no rompe el comportamiento de los agentes."""

    def test_tutor_agent_still_returns_response_with_bound_tools(self):
        """tutor_agent retorna 'response' aunque llm_tutor tenga bind_tools()."""
        with patch("agents.tutor_agent._call_gemini", return_value="Mi respuesta"), \
             patch("agents.tutor_agent.get_all_concepts", return_value=[]), \
             patch("agents.tutor_agent.web_search", return_value={"results": []}), \
             patch("os.environ.get", return_value="fake-key"), \
             patch("agents.tutor_agent.ChatGoogleGenerativeAI") as MockLLM:
            # El mock de bind_tools() devuelve otro mock (simula LLM con tools)
            MockLLM.return_value.bind_tools.return_value = MockLLM.return_value
            from agents.tutor_agent import tutor_agent
            state = {
                "user_input": "¿Qué es RAG?",
                "user_context": "",
                "mode": "question",
                "user_id": 1,
                "user_profile": {},
                "sources": [],
                "diagram_svg": "",
                "suggested_concepts": [],
            }
            result = tutor_agent(state)
        self.assertIn("response", result)
        self.assertTrue(len(result["response"]) > 0)

    def test_nura_tools_imported_in_capture_agent(self):
        """capture_agent importa _NURA_TOOLS sin error."""
        import agents.capture_agent as ca
        self.assertTrue(hasattr(ca, "_NURA_TOOLS"))

    def test_nura_tools_imported_in_classifier_agent(self):
        """classifier_agent importa _NURA_TOOLS sin error."""
        import agents.classifier_agent as cls
        self.assertTrue(hasattr(cls, "_NURA_TOOLS"))

    def test_nura_tools_imported_in_connector_agent(self):
        """connector_agent importa _NURA_TOOLS sin error."""
        import agents.connector_agent as con
        self.assertTrue(hasattr(con, "_NURA_TOOLS"))

    def test_nura_tools_imported_in_tutor_agent(self):
        """tutor_agent importa _NURA_TOOLS sin error."""
        import agents.tutor_agent as ta
        self.assertTrue(hasattr(ta, "_NURA_TOOLS"))
        self.assertEqual(len(ta._NURA_TOOLS), 6)


class TestOriginalInterfacesUnchanged(unittest.TestCase):
    """(5) Las interfaces públicas originales siguen intactas."""

    def test_classify_concept_still_callable_as_function(self):
        """classify_concept sigue siendo una función Python regular."""
        from tools.classifier_tool import classify_concept
        import inspect
        self.assertTrue(callable(classify_concept))
        # Debe ser una función, no un StructuredTool
        self.assertTrue(inspect.isfunction(classify_concept))

    def test_find_connections_still_callable_as_function(self):
        """find_connections sigue siendo una función Python regular."""
        from tools.connector_tool import find_connections
        import inspect
        self.assertTrue(inspect.isfunction(find_connections))

    def test_web_search_still_callable_as_function(self):
        """web_search sigue siendo una función Python regular."""
        from tools.search_tool import web_search
        import inspect
        self.assertTrue(inspect.isfunction(web_search))

    def test_classification_error_still_importable(self):
        """ClassificationError sigue siendo importable desde classifier_tool."""
        from tools.classifier_tool import ClassificationError
        self.assertTrue(issubclass(ClassificationError, Exception))

    def test_classifier_system_prompt_still_importable(self):
        """CLASSIFIER_SYSTEM_PROMPT sigue siendo importable."""
        from tools.classifier_tool import CLASSIFIER_SYSTEM_PROMPT
        self.assertIsInstance(CLASSIFIER_SYSTEM_PROMPT, str)
        self.assertTrue(len(CLASSIFIER_SYSTEM_PROMPT) > 0)

    def test_connector_system_prompt_still_importable(self):
        """CONNECTOR_SYSTEM_PROMPT sigue siendo importable."""
        from tools.connector_tool import CONNECTOR_SYSTEM_PROMPT
        self.assertIsInstance(CONNECTOR_SYSTEM_PROMPT, str)
        self.assertTrue(len(CONNECTOR_SYSTEM_PROMPT) > 0)


if __name__ == "__main__":
    unittest.main()
