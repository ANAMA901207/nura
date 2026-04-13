"""
tests/test_sprint17.py
======================
Harness del Sprint 17 — diagramas SVG automáticos en respuestas del tutor.

Verifica:
1. should_generate_diagram retorna bool.
2. generate_diagram_svg retorna string con 'viewBox' cuando tiene nodos.
3. Fallo de API en diagram_tool retorna valores seguros sin excepción.
4. tutor_agent continúa normalmente (con diagram_svg en estado) cuando
   diagram_tool falla.
5. render_diagram no lanza errores con SVG válido.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestShouldGenerateDiagram(unittest.TestCase):
    """(1) should_generate_diagram retorna bool."""

    def test_returns_true_when_gemini_says_yes(self):
        """Retorna True cuando Gemini indica needs_diagram=True."""
        mock_result = {"needs_diagram": True, "diagram_type": "flow", "reason": "test"}
        with patch("tools.diagram_tool._call_gemini_json", return_value=mock_result):
            from tools.diagram_tool import should_generate_diagram
            result = should_generate_diagram("texto de prueba", {})
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_returns_false_when_gemini_says_no(self):
        """Retorna False cuando Gemini indica needs_diagram=False."""
        mock_result = {"needs_diagram": False, "diagram_type": "none", "reason": "simple"}
        with patch("tools.diagram_tool._call_gemini_json", return_value=mock_result):
            from tools.diagram_tool import should_generate_diagram
            result = should_generate_diagram("texto simple", {})
        self.assertIsInstance(result, bool)
        self.assertFalse(result)

    def test_returns_bool_type_always(self):
        """El tipo de retorno es siempre bool, incluso con respuesta parcial."""
        with patch("tools.diagram_tool._call_gemini_json", return_value={}):
            from tools.diagram_tool import should_generate_diagram
            result = should_generate_diagram("texto", {})
        self.assertIsInstance(result, bool)

    def test_returns_false_for_empty_text(self):
        """Retorna False sin llamar a Gemini si el texto está vacío."""
        with patch("tools.diagram_tool._call_gemini_json") as mock_llm:
            from tools.diagram_tool import should_generate_diagram
            result = should_generate_diagram("", {})
        self.assertFalse(result)
        mock_llm.assert_not_called()


class TestGenerateDiagramSvg(unittest.TestCase):
    """(2) generate_diagram_svg retorna string con 'viewBox' cuando tiene nodos."""

    _MOCK_DATA = {
        "nodes": [
            {"id": "n1", "label": "Input", "color": "#60a0ff"},
            {"id": "n2", "label": "Proceso", "color": "#cba6f7"},
            {"id": "n3", "label": "Output", "color": "#a6e3a1"},
        ],
        "edges": [
            {"from": "n1", "to": "n2", "label": "alimenta"},
            {"from": "n2", "to": "n3", "label": "produce"},
        ],
        "title": "Diagrama de prueba",
    }

    def test_returns_svg_with_viewbox(self):
        """El SVG generado contiene el atributo viewBox."""
        with patch("tools.diagram_tool._call_gemini_json", return_value=self._MOCK_DATA):
            from tools.diagram_tool import generate_diagram_svg
            svg = generate_diagram_svg("texto de prueba", "flow")
        self.assertIsInstance(svg, str)
        self.assertIn("viewBox", svg)

    def test_svg_contains_node_labels(self):
        """El SVG contiene las etiquetas de los nodos."""
        with patch("tools.diagram_tool._call_gemini_json", return_value=self._MOCK_DATA):
            from tools.diagram_tool import generate_diagram_svg
            svg = generate_diagram_svg("texto", "hierarchy")
        self.assertIn("Input", svg)
        self.assertIn("Proceso", svg)

    def test_svg_contains_title(self):
        """El SVG contiene el título del diagrama."""
        with patch("tools.diagram_tool._call_gemini_json", return_value=self._MOCK_DATA):
            from tools.diagram_tool import generate_diagram_svg
            svg = generate_diagram_svg("texto", "flow")
        self.assertIn("Diagrama de prueba", svg)

    def test_returns_empty_for_none_type(self):
        """Retorna cadena vacía cuando diagram_type es 'none'."""
        from tools.diagram_tool import generate_diagram_svg
        result = generate_diagram_svg("texto", "none")
        self.assertEqual(result, "")

    def test_returns_empty_for_empty_text(self):
        """Retorna cadena vacía cuando concept_text está vacío."""
        from tools.diagram_tool import generate_diagram_svg
        result = generate_diagram_svg("", "flow")
        self.assertEqual(result, "")

    def test_returns_empty_when_no_nodes(self):
        """Retorna cadena vacía cuando Gemini devuelve lista de nodos vacía."""
        empty_data = {"nodes": [], "edges": [], "title": "Sin nodos"}
        with patch("tools.diagram_tool._call_gemini_json", return_value=empty_data):
            from tools.diagram_tool import generate_diagram_svg
            result = generate_diagram_svg("texto", "flow")
        self.assertEqual(result, "")


class TestDiagramToolApiFailure(unittest.TestCase):
    """(3) Fallo de API retorna valores seguros sin excepción."""

    def test_should_generate_diagram_returns_false_on_api_error(self):
        """should_generate_diagram retorna False cuando _call_gemini_json lanza."""
        with patch("tools.diagram_tool._call_gemini_json", side_effect=Exception("API error")):
            from tools.diagram_tool import should_generate_diagram
            result = should_generate_diagram("texto con error de API", {})
        self.assertFalse(result)

    def test_generate_diagram_svg_returns_empty_on_api_error(self):
        """generate_diagram_svg retorna '' cuando _call_gemini_json lanza."""
        with patch("tools.diagram_tool._call_gemini_json", side_effect=Exception("timeout")):
            from tools.diagram_tool import generate_diagram_svg
            result = generate_diagram_svg("texto con error", "flow")
        self.assertEqual(result, "")

    def test_no_exception_propagated_from_should_generate(self):
        """should_generate_diagram no propaga ninguna excepción."""
        with patch("tools.diagram_tool._call_gemini_json", side_effect=RuntimeError("crash")):
            from tools.diagram_tool import should_generate_diagram
            try:
                result = should_generate_diagram("texto", {})
            except Exception as exc:
                self.fail(f"should_generate_diagram propagó excepción: {exc}")
        self.assertFalse(result)


class TestTutorAgentWithDiagram(unittest.TestCase):
    """(4) tutor_agent continúa normalmente cuando diagram_tool falla."""

    def _make_state(self) -> dict:
        return {
            "user_input":   "¿Cómo funciona el algoritmo SM-2?",
            "user_context": "",
            "mode":         "question",
            "user_id":      1,
            "user_profile": {},
            "sources":      [],
            "diagram_svg":  "",
        }

    def test_diagram_svg_key_present_in_result(self):
        """tutor_agent siempre incluye 'diagram_svg' en el dict de retorno."""
        with patch("agents.tutor_agent._call_gemini", return_value="Respuesta del tutor"), \
             patch("agents.tutor_agent.get_all_concepts", return_value=[]), \
             patch("agents.tutor_agent.web_search", return_value={"results": []}), \
             patch("os.environ.get", return_value="fake-key"), \
             patch("agents.tutor_agent.ChatGoogleGenerativeAI"):
            # diagram_tool falla — el tutor debe continuar igualmente
            with patch("tools.diagram_tool.should_generate_diagram", side_effect=Exception("fallo")):
                from agents.tutor_agent import tutor_agent
                result = tutor_agent(self._make_state())

        self.assertIn("diagram_svg", result)
        self.assertIsInstance(result["diagram_svg"], str)

    def test_response_present_even_if_diagram_fails(self):
        """La respuesta del tutor está presente aunque diagram_tool falle."""
        with patch("agents.tutor_agent._call_gemini", return_value="Mi respuesta"), \
             patch("agents.tutor_agent.get_all_concepts", return_value=[]), \
             patch("agents.tutor_agent.web_search", return_value={"results": []}), \
             patch("os.environ.get", return_value="fake-key"), \
             patch("agents.tutor_agent.ChatGoogleGenerativeAI"), \
             patch("tools.diagram_tool.should_generate_diagram", side_effect=Exception("error")):
            from agents.tutor_agent import tutor_agent
            result = tutor_agent(self._make_state())

        self.assertIn("response", result)
        self.assertTrue(len(result["response"]) > 0)


class TestRenderDiagram(unittest.TestCase):
    """(5) render_diagram no lanza errores con SVG válido."""

    _SAMPLE_SVG = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 300">'
        '<rect width="600" height="300" fill="#1e1e2e"/>'
        '<text x="300" y="150" fill="#cdd6f4">Test</text>'
        '</svg>'
    )

    def test_renders_without_error(self):
        """render_diagram no lanza excepciones con un SVG válido."""
        mock_st = MagicMock()
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            import importlib
            import ui.components as comp
            importlib.reload(comp)
            try:
                comp.render_diagram(self._SAMPLE_SVG)
            except Exception as exc:
                self.fail(f"render_diagram lanzó excepción: {exc}")

    def test_no_op_for_empty_string(self):
        """render_diagram no llama a st.markdown si el SVG está vacío."""
        mock_st = MagicMock()
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            import importlib
            import ui.components as comp
            importlib.reload(comp)
            comp.render_diagram("")
            mock_st.markdown.assert_not_called()

    def test_svg_content_embedded_in_output(self):
        """El SVG pasado se embebe en el HTML generado por st.markdown."""
        calls = []
        mock_st = MagicMock()
        mock_st.markdown.side_effect = lambda html, **kw: calls.append(html)

        with patch.dict("sys.modules", {"streamlit": mock_st}):
            import importlib
            import ui.components as comp
            importlib.reload(comp)
            comp.render_diagram(self._SAMPLE_SVG)

        self.assertTrue(len(calls) > 0, "st.markdown no fue llamado")
        self.assertIn("viewBox", calls[0])


class TestBuildSvgInternal(unittest.TestCase):
    """Tests de la función interna _build_svg."""

    def test_single_node_svg(self):
        """SVG con un solo nodo incluye viewBox y el label del nodo."""
        from tools.diagram_tool import _build_svg
        nodes = [{"id": "n1", "label": "Nodo único", "color": "#60a0ff"}]
        svg = _build_svg(nodes, [], "Prueba")
        self.assertIn("viewBox", svg)
        self.assertIn("Nodo único", svg)

    def test_edges_only_between_existing_nodes(self):
        """Las aristas con nodos inexistentes se ignoran sin error."""
        from tools.diagram_tool import _build_svg
        nodes = [{"id": "n1", "label": "A", "color": "#60a0ff"}]
        edges = [{"from": "n1", "to": "n_inexistente", "label": "x"}]
        try:
            svg = _build_svg(nodes, edges, "Test")
        except Exception as exc:
            self.fail(f"_build_svg lanzó excepción con arista inválida: {exc}")
        self.assertIn("viewBox", svg)

    def test_html_in_label_is_escaped(self):
        """Los caracteres HTML en las etiquetas se escapan correctamente."""
        from tools.diagram_tool import _build_svg
        nodes = [{"id": "n1", "label": "<script>alert(1)</script>", "color": "#60a0ff"}]
        svg = _build_svg(nodes, [], "")
        self.assertNotIn("<script>", svg)


if __name__ == "__main__":
    unittest.main()
