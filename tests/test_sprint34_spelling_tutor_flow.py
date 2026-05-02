"""
tests/test_sprint34_spelling_tutor_flow.py
==========================================
Flujo ortografía → confirmación (chat) → pregunta: la respuesta del tutor
debe ser texto plano (content multipart de Gemini/LangChain).

Sin llamadas reales a la API: mocks de LLM y BD mínimos.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")


def test_message_content_to_str_dict_type_text():
    from agents.message_content import message_content_to_str

    assert message_content_to_str({"type": "text", "text": "Hola"}) == "Hola"


def test_message_content_to_str_multipart_list():
    from agents.message_content import message_content_to_str

    blocks = [
        {"type": "text", "text": "Parte A "},
        {"type": "text", "text": "parte B."},
    ]
    assert message_content_to_str(blocks) == "Parte A parte B."


def test_spelling_then_si_then_question_tutor_returns_plain_string():
    """
    Ortografía detectada → 'si' es modo chat → pregunta con tutor + tools
    y AIMessage.content en formato lista: ``response`` debe ser str legible.
    """
    from agents.capture_agent import capture_agent
    from agents import tutor_agent

    profile: dict = {}
    base = {
        "user_input":             "",
        "user_context":           "",
        "current_concept":        None,
        "all_concepts":           [],
        "new_connections":        [],
        "response":               "",
        "mode":                   "",
        "user_id":                1,
        "quiz_questions":         [],
        "sources":                [],
        "insight_message":        "",
        "clarification_options":  [],
        "spelling_suggestion":    "",
        "user_profile":           profile,
        "diagram_svg":            "",
        "suggested_concepts":     [],
    }

    with patch("agents.capture_agent.get_concept_by_term", return_value=None):
        with patch(
            "agents.capture_agent._check_spelling",
            return_value={"has_typo": True, "suggested": "algoritmo"},
        ):
            r_spell = capture_agent({**base, "user_input": "algorimto"})

    assert r_spell["mode"] == "spelling"
    assert "algoritmo" in r_spell["response"]
    assert "Quisiste" in r_spell["response"] or "quisiste" in r_spell["response"].lower()

    r_si = capture_agent({**base, "user_input": "si"})
    assert r_si["mode"] == "chat"

    fake_final = MagicMock()
    fake_final.content = [{"type": "text", "text": "Una explicación breve del algoritmo."}]
    fake_final.tool_calls = []
    mock_bound = MagicMock()
    mock_bound.invoke.return_value = fake_final

    llm_calls: list[int] = []

    def _make_llm(*_a, **_k):
        llm_calls.append(1)
        m = MagicMock()
        if len(llm_calls) == 1:
            pass  # solo se usa con _call_gemini (mockeado)
        else:
            m.bind_tools.return_value = mock_bound
        return m

    fake_tool = MagicMock()
    fake_tool.name = "lookup_concepts"
    fake_tool.invoke = MagicMock(return_value="{}")

    q_state = {**base, "mode": "question", "user_input": "¿Qué es un algoritmo?"}

    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=False):
        with patch.object(tutor_agent, "get_all_concepts", return_value=[]):
            with patch.object(
                tutor_agent,
                "build_similar_concepts_prompt_section",
                return_value="",
            ):
                with patch.object(tutor_agent, "_parse_needs_search", return_value=False):
                    with patch.object(
                        tutor_agent,
                        "_call_gemini",
                        return_value='{"needs_search": false}',
                    ):
                        with patch.object(
                            tutor_agent,
                            "ChatGoogleGenerativeAI",
                            side_effect=_make_llm,
                        ):
                            with patch.object(
                                tutor_agent,
                                "TUTOR_BIND_TOOLS",
                                [fake_tool],
                            ):
                                with patch(
                                    "tools.concept_detector_tool.detect_new_concepts",
                                    return_value=[],
                                ):
                                    with patch(
                                        "db.operations.save_last_tutor_response",
                                    ):
                                        with patch(
                                            "tools.diagram_tool.should_generate_diagram",
                                            return_value=False,
                                        ):
                                            out = tutor_agent.tutor_agent(q_state)

    resp = out.get("response", "")
    assert isinstance(resp, str)
    assert "{'type'" not in resp and '{"type"' not in resp
    assert "explicación breve" in resp.lower() or "algoritmo" in resp.lower()
    assert "http" not in resp.lower()
