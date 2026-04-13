"""
tests/test_chat_mode.py
=======================
Harness de verificación para el modo conversacional 'chat'.

Pruebas incluidas
-----------------
1. 'no entiendo'     → capture_agent establece mode='chat'.
2. 'hola'            → mode='chat'.
3. 'gracias'         → mode='chat'.
4. 'ok'              → mode='chat'.
5. 'qué puedes hacer'→ mode='chat'.
6. Término real      → NO mode='chat' (no debe capturarse como chat).
7. Pregunta real     → NO mode='chat'.
8. tutor_agent en mode='chat' responde sin llamar al LLM y sin error.
9. La respuesta a 'no entiendo' contiene una invitación a aclarar la duda.
10. El grafo completo con input 'hola' devuelve una respuesta sin tocar la BD.
"""

from __future__ import annotations

import sys
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Apuntar la BD a un fichero temporal para no contaminar la BD real
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ.setdefault("NURA_DB_PATH", _tmp_db.name)

from db.schema import init_db
from agents.capture_agent import _is_chat, capture_agent
from agents.tutor_agent import _chat_response, tutor_agent
from agents.state import NuraState

init_db()


def _make_state(user_input: str, mode: str = "") -> NuraState:
    """Crea un NuraState mínimo para pruebas de captura."""
    return {
        "user_input": user_input,
        "user_context": "",
        "current_concept": None,
        "all_concepts": [],
        "new_connections": [],
        "response": "",
        "mode": mode,
        "quiz_questions": [],
        "sources": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1-7: detección de _is_chat y capture_agent
# ─────────────────────────────────────────────────────────────────────────────

class TestIsChatDetection(unittest.TestCase):
    """Verifica que _is_chat() clasifica correctamente las expresiones."""

    def test_no_entiendo_is_chat(self):
        self.assertTrue(_is_chat("no entiendo"))

    def test_no_entiendo_accent_is_chat(self):
        self.assertTrue(_is_chat("no entendí"))

    def test_hola_is_chat(self):
        self.assertTrue(_is_chat("hola"))

    def test_gracias_is_chat(self):
        self.assertTrue(_is_chat("gracias"))

    def test_ok_is_chat(self):
        self.assertTrue(_is_chat("ok"))

    def test_que_puedes_hacer_is_chat(self):
        self.assertTrue(_is_chat("qué puedes hacer"))

    def test_ayuda_is_chat(self):
        self.assertTrue(_is_chat("ayuda"))

    def test_si_is_chat(self):
        self.assertTrue(_is_chat("sí"))

    def test_no_standalone_is_chat(self):
        self.assertTrue(_is_chat("no"))

    def test_perfecto_is_chat(self):
        self.assertTrue(_is_chat("perfecto"))

    def test_real_term_is_not_chat(self):
        """Un término técnico no debe detectarse como chat."""
        self.assertFalse(_is_chat("amortización"))

    def test_real_question_is_not_chat(self):
        """Una pregunta larga no debe detectarse como chat."""
        self.assertFalse(_is_chat("cómo funciona el algoritmo de backpropagation"))

    def test_long_input_is_not_chat(self):
        """Un input de más de 6 palabras nunca es chat aunque empiece con hola."""
        self.assertFalse(_is_chat("hola me gustaría aprender sobre redes neuronales hoy"))


class TestCaptureAgentChatMode(unittest.TestCase):
    """Verifica que capture_agent establece mode='chat' correctamente."""

    def test_no_entiendo_sets_chat_mode(self):
        result = capture_agent(_make_state("no entiendo"))
        self.assertEqual(result["mode"], "chat")

    def test_hola_sets_chat_mode(self):
        result = capture_agent(_make_state("hola"))
        self.assertEqual(result["mode"], "chat")

    def test_gracias_sets_chat_mode(self):
        result = capture_agent(_make_state("gracias"))
        self.assertEqual(result["mode"], "chat")

    def test_chat_does_not_touch_db(self):
        """En modo chat no debe haber current_concept ni all_concepts poblados."""
        result = capture_agent(_make_state("ok"))
        self.assertIsNone(result["current_concept"])

    def test_real_term_is_not_chat_mode(self):
        """Un término nuevo real no debe producir mode='chat'."""
        # Usamos un término que no exista en la BD temporal
        result = capture_agent(_make_state("derivada_financiera_test_xyz"))
        self.assertNotEqual(result.get("mode"), "chat")


# ─────────────────────────────────────────────────────────────────────────────
# 8-9: tutor_agent fast-path
# ─────────────────────────────────────────────────────────────────────────────

class TestTutorAgentChatFastPath(unittest.TestCase):
    """Verifica que tutor_agent responde sin LLM cuando mode='chat'."""

    def test_chat_response_no_llm_call(self):
        """tutor_agent en mode='chat' no debe invocar ChatGoogleGenerativeAI."""
        state = _make_state("no entiendo", mode="chat")
        with patch("agents.tutor_agent.ChatGoogleGenerativeAI") as mock_llm:
            result = tutor_agent(state)
            mock_llm.assert_not_called()
        self.assertIn("response", result)
        self.assertIsInstance(result["response"], str)
        self.assertTrue(len(result["response"]) > 0)

    def test_no_entiendo_response_invites_clarification(self):
        """La respuesta a 'no entiendo' debe invitar al usuario a aclarar."""
        reply = _chat_response("no entiendo")
        # Debe contener alguna forma de invitación a seguir hablando
        self.assertTrue(
            any(kw in reply.lower() for kw in ["qué", "que", "cuentame", "cuéntame", "clara", "claro"]),
            f"Respuesta no invita a aclarar: {reply!r}",
        )

    def test_hola_response_is_greeting(self):
        reply = _chat_response("hola")
        self.assertTrue(len(reply) > 10)

    def test_sources_empty_in_chat_mode(self):
        """El fast-path siempre devuelve sources vacío."""
        state = _make_state("gracias", mode="chat")
        result = tutor_agent(state)
        self.assertEqual(result.get("sources", []), [])


# ─────────────────────────────────────────────────────────────────────────────
# 10: integración end-to-end con el grafo (sin LLM)
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphChatRoute(unittest.TestCase):
    """Verifica el flujo completo capture → tutor (chat fast-path)."""

    def test_graph_chat_returns_response_without_llm(self):
        """El grafo completo con 'hola' devuelve una respuesta sin LLM."""
        from agents.graph import build_graph

        graph = build_graph()
        initial_state: NuraState = {
            "user_input": "hola",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "",
            "quiz_questions": [],
            "sources": [],
        }

        with patch("agents.tutor_agent.ChatGoogleGenerativeAI") as mock_llm:
            result = graph.invoke(initial_state)
            mock_llm.assert_not_called()

        self.assertEqual(result["mode"], "chat")
        self.assertIsInstance(result["response"], str)
        self.assertTrue(len(result["response"]) > 0)


# ─────────────────────────────────────────────────────────────────────────────
# runner
# ─────────────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestIsChatDetection,
        TestCaptureAgentChatMode,
        TestTutorAgentChatFastPath,
        TestGraphChatRoute,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    passed = failed = 0
    for test in suite:
        result = unittest.TestResult()
        test.run(result)
        name = str(test).split(" ")[0]
        if result.errors or result.failures:
            msg = (result.errors or result.failures)[0][1].splitlines()[-1]
            print(f"  FAIL  {name}: {msg}")
            failed += 1
        else:
            print(f"  OK    {name}")
            passed += 1

    total = passed + failed
    print(f"\n{passed}/{total} passed", "OK" if failed == 0 else "-- hay fallos")


if __name__ == "__main__":
    _run_all()
