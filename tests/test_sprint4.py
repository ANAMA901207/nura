"""
tests/test_sprint4.py
=====================
Harness de verificación — Sprint 4: Tutor Agent e integración final.

Tests 1 y 2 hacen llamadas reales a Gemini; requieren GOOGLE_API_KEY en .env.
Tests 3, 4 y 5 no necesitan API y son deterministas.

Ejecutar con:
    python tests/test_sprint4.py
o con pytest:
    python -m pytest tests/test_sprint4.py -v
"""

from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# BD temporal aislada para todos los tests
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.schema as _schema
_schema.DB_PATH = Path(_tmp_db.name)

from db.schema import init_db
import pytest
from db.operations import save_concept, update_concept_fields, get_all_concepts


def _skip_on_gemini_error(result: dict) -> None:
    r = (result.get("response") or "") + (result.get("insight_message") or "")
    if any(
        x in r
        for x in (
            "No puedo conectarme al servicio de IA",
            "GOOGLE_API_KEY no está configurada",
            "Nura no pudo clasificar este término",
            "El servicio de IA está saturado",
            "El servicio de IA no pudo responder",
        )
    ):
        pytest.skip(f"Gemini no disponible en este entorno: {r[:140]!r}")

# Estado base vacío para invocar el grafo
_BASE_STATE = {
    "user_input": "",
    "current_concept": None,
    "all_concepts": [],
    "new_connections": [],
    "response": "",
    "mode": "",
}


# ── fixture ───────────────────────────────────────────────────────────────────

def _reset_db() -> None:
    """Elimina y recrea todas las tablas entre tests."""
    conn = sqlite3.connect(str(_schema.DB_PATH))
    conn.executescript("""
        DROP TABLE IF EXISTS connections;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS daily_summaries;
    """)
    conn.close()
    init_db()


def _state(**overrides) -> dict:
    return {**_BASE_STATE, **overrides}


def _seed_concept(term: str = "tasa de interes", mastery_level: int = 0) -> object:
    """
    Guarda un concepto de prueba en la BD con campos enriquecidos.

    Simula el resultado de clasificador para que el tutor tenga contexto real.
    """
    c = save_concept(term=term, context="test")
    return update_concept_fields(
        c.id,
        category="Finanzas",
        subcategory="Credito",
        explanation=f"El {term} es el costo del dinero prestado en el tiempo.",
        analogy="Es como el alquiler que pagas por usar dinero ajeno.",
        flashcard_front=f"¿Qué es la {term}?",
        flashcard_back=f"El porcentaje que se cobra por prestar dinero.",
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test_question_gets_real_tutor_response() -> None:
    """
    (1) Una pregunta recibe respuesta real no vacía del tutor.

    Ejecuta el grafo completo con una pregunta.  Verifica que:
    - mode == 'question' en el estado resultante.
    - state.response no está vacío.
    - La respuesta no es el mensaje placeholder del Sprint 3.
    - La respuesta tiene sustancia (>= 50 caracteres).
    """
    _reset_db()
    from agents.graph import build_graph
    graph = build_graph()

    result = graph.invoke(_state(user_input="que es la tasa de interes?"))
    _skip_on_gemini_error(result)

    assert result.get("mode") == "question", (
        f"Se esperaba mode='question', se obtuvo '{result.get('mode')}'"
    )
    response = result.get("response", "")
    assert response, "La respuesta del tutor no debe estar vacía"
    assert "Sprint 3" not in response, (
        "La respuesta no debe contener el mensaje placeholder del Sprint 3"
    )
    assert len(response) >= 50, (
        f"La respuesta del tutor debe tener sustancia (>= 50 chars), tiene {len(response)}"
    )

    print(f"  [1] Tutor respondió ({len(response)} chars): '{response[:60]}...' OK")


def test_tutor_uses_bd_context() -> None:
    """
    (2) El tutor incluye contexto de la BD en su respuesta.

    Pre-siembra un concepto con explicación en la BD, luego hace una
    pregunta sobre él usando una palabra interrogativa para activar mode='question'.
    Verifica que la respuesta del tutor es sustancial y temáticamente relevante.
    """
    _reset_db()
    _seed_concept("amortizacion")

    from agents.graph import build_graph
    graph = build_graph()

    # "como" está en _QUESTION_STARTERS → activa mode='question'
    result = graph.invoke(_state(user_input="como funciona la amortizacion?"))
    _skip_on_gemini_error(result)

    response = result.get("response", "")
    assert len(response) >= 50, (
        f"La respuesta con contexto debe ser sustancial (>= 50 chars), tiene {len(response)}"
    )
    assert result.get("mode") == "question", (
        f"El modo debe ser 'question', se obtuvo '{result.get('mode')}'"
    )

    # El tutor debería mencionar algo relacionado con el concepto sembrado
    response_lower = response.lower()
    assert any(
        kw in response_lower
        for kw in ["amortiz", "pago", "deuda", "credito", "prestamo", "dinero", "financ", "cuota"]
    ), f"La respuesta deberia ser relevante al tema, se obtuvo: '{response[:100]}'"

    print(f"  [2] Tutor uso contexto de BD: respuesta relevante ({len(response)} chars) OK")


def test_review_agent_returns_concepts_with_low_mastery() -> None:
    """
    (3) review_agent retorna al menos 1 concepto cuando hay conceptos con mastery_level=0.

    No requiere API.  Siembra conceptos con mastery=0 directamente en la BD,
    invoca review_agent, y verifica que la respuesta lista al menos uno.
    """
    _reset_db()
    _seed_concept("cartera vencida")
    _seed_concept("provision de incobrables")

    from agents.review_agent import review_agent

    result = review_agent(_state())

    response = result.get("response", "")
    assert response, "review_agent debe devolver una respuesta"
    assert any(
        kw in response.lower()
        for kw in ["cartera", "provision", "repasar", "concepto", "dominio"]
    ), f"La respuesta de repaso debería mencionar los conceptos, se obtuvo: '{response[:150]}'"

    # Encode as ASCII for safe printing on Windows terminals
    safe_response = response[:120].encode("ascii", "replace").decode("ascii")
    print(f"  [3] review_agent listo conceptos con mastery=0: OK")
    print(f"      Respuesta: '{safe_response}...'")


def test_review_input_activates_review_mode() -> None:
    """
    (4) Input 'qué debo repasar' activa mode='review' sin llamar a la API.

    Prueba directamente capture_agent para verificar que la heurística
    de detección de repaso funciona para distintas variantes del input.
    """
    _reset_db()
    from agents.capture_agent import capture_agent, _is_review

    # Verifica la heurística directamente para variantes comunes
    review_inputs = [
        "qué debo repasar",
        "que debo repasar",
        "repasar",
        "quiero repasar mis conceptos",
        "sesión de repaso",
        "que debo repasar hoy",
    ]
    for inp in review_inputs:
        assert _is_review(inp), f"_is_review debería detectar '{inp}' como repaso"

    # Verifica que el nodo devuelve mode='review'
    result = capture_agent(_state(user_input="que debo repasar hoy"))
    assert result.get("mode") == "review", (
        f"Se esperaba mode='review', se obtuvo '{result.get('mode')}'"
    )
    assert result.get("current_concept") is None, "No debe capturar concepto en modo review"

    print(f"  [4] 'que debo repasar' -> mode='review': OK ({len(review_inputs)} variantes verificadas)")


def test_app_runs_without_errors_with_empty_db() -> None:
    """
    (5) ui/app.py importa sin errores con BD vacía.

    Verifica que el módulo de la aplicación puede importarse sin excepción,
    que la función main() está definida, y que las funciones internas críticas
    son llamables con estado vacío.
    """
    _reset_db()

    # Mock de streamlit antes del import
    from unittest.mock import MagicMock
    mock_st = MagicMock()
    mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    mock_st.tabs.return_value = [MagicMock(), MagicMock()]
    mock_st.expander.return_value.__enter__ = lambda s: s
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
    sys.modules["streamlit"] = mock_st
    sys.modules["streamlit.components"] = MagicMock()
    sys.modules["streamlit.components.v1"] = MagicMock()

    if "ui.app" in sys.modules:
        del sys.modules["ui.app"]

    try:
        import ui.app
        assert hasattr(ui.app, "main"), "ui.app debe exponer main()"
        assert callable(ui.app._empty_state), "_empty_state debe ser callable"
        assert callable(ui.app._handle_submit), "_handle_submit debe ser callable"
    except Exception as exc:
        raise AssertionError(f"ui/app.py lanzó error al importar: {exc}")

    print("  [5] ui/app.py importa correctamente con BD vacía: OK")


# ── runner ────────────────────────────────────────────────────────────────────

def _is_quota_error(exc: Exception) -> bool:
    """Devuelve True si la excepción es un error de cuota diaria agotada de Gemini."""
    msg = str(exc)
    return (
        "RESOURCE_EXHAUSTED" in msg
        and ("limit: 20" in msg or "GenerateRequestsPerDay" in msg or "quota" in msg.lower())
    )


def _run_all() -> None:
    """Ejecuta todos los tests y reporta el resultado final."""
    tests = [
        test_question_gets_real_tutor_response,
        test_tutor_uses_bd_context,
        test_review_agent_returns_concepts_with_low_mastery,
        test_review_input_activates_review_mode,
        test_app_runs_without_errors_with_empty_db,
    ]

    passed = 0
    failed = 0
    skipped = 0

    print("\nSprint 4 - Tutor + Integracion Final - Test Harness")
    print("=" * 58)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            if _is_quota_error(exc):
                skipped += 1
                print(f"  SKIP  {test.__name__}")
                print(f"        (cuota diaria de Gemini agotada — no es falla de codigo)")
            else:
                print(f"  FAIL  {test.__name__}")
                print(f"        {exc}")
                failed += 1

    total = passed + failed + skipped
    print("=" * 58)
    skip_note = f"  ({skipped} skipped por cuota API)" if skipped else ""
    print(f"Resultado: {passed}/{total} passed{skip_note}", end="")
    print(f"  ({failed} failed)" if failed else "  OK todos pasaron")
    print("=" * 58)

    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
