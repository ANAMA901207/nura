"""
tests/test_sprint5.py
=====================
Harness de verificación — Sprint 5: mejoras de clasificación y fix de conceptos vacíos.

Test 1 hace una llamada real a Gemini para verificar que user_context llega al prompt.
Tests 2-5 son deterministas y no requieren API.

Ejecutar con:
    python tests/test_sprint5.py
"""

from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# BD temporal aislada
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.schema as _schema
_schema.DB_PATH = Path(_tmp_db.name)

from db.schema import init_db
from db.operations import (
    save_concept,
    get_concept_by_term,
    get_unclassified_concepts,
    update_concept_classification,
    get_concept_by_id,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

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


# ── tests ─────────────────────────────────────────────────────────────────────

def test_classifier_receives_user_context_in_prompt() -> None:
    """
    (1) El clasificador recibe user_context y lo incluye en el prompt al llamar al LLM.

    Verifica que classify_concept construye el texto humano con la línea
    'Contexto adicional del usuario: ...' cuando se pasa user_context no vacío.
    Para hacerlo determinista (sin API real), parchea ChatGoogleGenerativeAI.invoke()
    con un stub que captura los mensajes y devuelve JSON válido.
    """
    from unittest.mock import MagicMock, patch

    captured_messages = []
    fake_response = MagicMock()
    fake_response.content = (
        '{"category":"Finanzas","subcategory":"Credito","explanation":"test",'
        '"how_it_works":"","schema":"","analogy":"","example":"",'
        '"flashcard_front":"P?","flashcard_back":"R."}'
    )

    def fake_invoke(messages):
        captured_messages.extend(messages)
        return fake_response

    with patch(
        "tools.classifier_tool.ChatGoogleGenerativeAI"
    ) as MockLLM:
        instance = MockLLM.return_value
        instance.invoke.side_effect = fake_invoke

        # Importar después del patch para que use el mock
        from tools.classifier_tool import classify_concept
        result = classify_concept(
            term="tasa de interes",
            context="libro de finanzas",
            user_context="escuchado en clase de riesgo crediticio",
        )

    # Verificar que se pasó un mensaje con el user_context
    assert captured_messages, "El LLM debe haber recibido mensajes"
    human_msg = next((m for m in captured_messages if hasattr(m, "content") and "tasa" in str(m.content)), None)
    assert human_msg is not None, "Debe haber un mensaje con el término"
    assert "escuchado en clase de riesgo crediticio" in str(human_msg.content), (
        "user_context debe aparecer en el prompt enviado al LLM"
    )
    assert result.get("category") == "Finanzas", "El JSON debe parsearse correctamente"

    print("  [1] classify_concept incluye user_context en el prompt: OK")


def test_duplicate_term_unclassified_returns_existing_without_error() -> None:
    """
    (2) Término duplicado con is_classified=False devuelve el concepto existente sin ValueError.

    Guarda un concepto (is_classified queda en False por defecto),
    luego intenta guardarlo de nuevo.  Debe retornar el mismo concepto
    sin lanzar ValueError.
    """
    _reset_db()

    # Primera inserción
    c1 = save_concept("amortizacion", context="primer guardado")
    assert not c1.is_classified, "Un concepto recién guardado debe tener is_classified=False"

    # Segunda inserción del mismo término — debe devolver el existente
    c2 = save_concept("amortizacion", context="segundo intento")
    assert c2.id == c1.id, (
        f"save_concept debe devolver el concepto existente (id={c1.id}), "
        f"se obtuvo id={c2.id}"
    )
    assert not c2.is_classified, "El concepto devuelto debe seguir sin estar clasificado"

    print("  [2] Termino duplicado con is_classified=False devuelve existente sin ValueError: OK")


def test_classification_error_does_not_save_empty_classification() -> None:
    """
    (3) ClassificationError no guarda clasificación vacía en la BD.

    Simula un fallo del clasificador con un mock que lanza ClassificationError.
    Verifica que el concepto en la BD sigue con is_classified=False y los
    campos de clasificación vacíos después del intento fallido.
    """
    _reset_db()
    from unittest.mock import patch
    from tools.classifier_tool import ClassificationError
    from agents.classifier_agent import classifier_agent

    # Prepara un concepto sin clasificar
    concept = save_concept("capital_de_trabajo", context="test")

    state = {
        "user_input": "capital_de_trabajo",
        "user_context": "",
        "current_concept": concept,
        "all_concepts": [concept],
        "new_connections": [],
        "response": "",
        "mode": "capture",
    }

    with patch(
        "agents.classifier_agent.classify_concept",
        side_effect=ClassificationError("Cuota agotada"),
    ):
        result = classifier_agent(state)

    # El agente debe devolver el concepto sin cambios y el mensaje amigable
    assert "🌙" in result.get("response", ""), (
        "La respuesta debe contener el mensaje amigable con 🌙"
    )
    assert result["current_concept"].id == concept.id

    # La BD debe seguir con is_classified=False
    stored = get_concept_by_id(concept.id)
    assert not stored.is_classified, (
        "El concepto en BD debe seguir con is_classified=False tras ClassificationError"
    )
    assert stored.category == "", (
        "El concepto en BD no debe tener categoría tras el fallo"
    )

    print("  [3] ClassificationError no guarda clasificacion vacia: OK")


def test_unclassified_concept_shows_badge() -> None:
    """
    (4) Concepto sin clasificar muestra el badge correcto en render_concept_card.

    Usa un mock de streamlit para verificar que render_concept_card
    incluye el texto 'Sin clasificar' en el HTML renderizado cuando
    is_classified=False.
    """
    _reset_db()
    from unittest.mock import MagicMock, call, patch

    # Mock streamlit — guardar el estado previo para restaurarlo al salir
    _prev_st = sys.modules.get("streamlit")
    mock_st = MagicMock()
    mock_st.expander.return_value.__enter__ = lambda s: s
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
    sys.modules["streamlit"] = mock_st

    if "ui.components" in sys.modules:
        del sys.modules["ui.components"]

    try:
        concept = save_concept("cartera_vencida", context="test")
        assert not concept.is_classified

        import ui.components as comp
        comp.render_concept_card(concept)

        # Verificar que alguna llamada a st.markdown contenía el badge de pendiente
        # Sprint 21: el badge cambió de 'Sin clasificar' a 'Pendiente'
        markdown_calls = [
            str(c.args[0])
            for c in mock_st.markdown.call_args_list
            if c.args
        ]
        found_badge = any("Pendiente" in s for s in markdown_calls)
        assert found_badge, (
            "render_concept_card debe incluir 'Pendiente' en el HTML "
            "cuando is_classified=False (Sprint 21: renombrado de 'Sin clasificar')"
        )
    finally:
        # Restaurar el mock anterior para no contaminar tests posteriores
        if _prev_st is not None:
            sys.modules["streamlit"] = _prev_st
        else:
            sys.modules.pop("streamlit", None)
        if "ui.components" in sys.modules:
            del sys.modules["ui.components"]

    print("  [4] Concepto sin clasificar muestra badge en render_concept_card: OK")


def test_update_concept_classification_persists_and_sets_flag() -> None:
    """
    (5) update_concept_classification persiste los cambios y marca is_classified=True.

    Crea un concepto sin clasificar, llama a update_concept_classification
    con un dict de campos, y verifica que la BD refleja los cambios y que
    is_classified es True después.
    """
    _reset_db()

    concept = save_concept("provision", context="test")
    assert not concept.is_classified

    updated = update_concept_classification(
        concept.id,
        {
            "category":       "Finanzas",
            "subcategory":    "Riesgo",
            "explanation":    "Reserva contable para pérdidas esperadas.",
            "flashcard_front": "¿Qué es una provisión?",
            "flashcard_back":  "Reserva contable para pérdidas esperadas.",
        },
    )

    assert updated.is_classified, "is_classified debe ser True tras la clasificación"
    assert updated.category == "Finanzas", "La categoría debe persistirse"
    assert updated.subcategory == "Riesgo", "La subcategoría debe persistirse"
    assert "contable" in updated.explanation, "La explicación debe persistirse"
    assert updated.flashcard_front == "¿Qué es una provisión?", "La flashcard debe persistirse"

    # Verificar directamente en BD
    stored = get_concept_by_id(concept.id)
    assert stored.is_classified
    assert stored.category == "Finanzas"

    print("  [5] update_concept_classification persiste cambios y sets is_classified=True: OK")


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
        test_classifier_receives_user_context_in_prompt,
        test_duplicate_term_unclassified_returns_existing_without_error,
        test_classification_error_does_not_save_empty_classification,
        test_unclassified_concept_shows_badge,
        test_update_concept_classification_persists_and_sets_flag,
    ]

    passed = 0
    failed = 0
    skipped = 0

    print("\nSprint 5 - Mejoras de clasificacion - Test Harness")
    print("=" * 56)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            if _is_quota_error(exc):
                skipped += 1
                print(f"  SKIP  {test.__name__}")
                print(f"        (cuota diaria Gemini agotada)")
            else:
                print(f"  FAIL  {test.__name__}")
                print(f"        {exc}")
                import traceback
                traceback.print_exc()
                failed += 1

    total = passed + failed + skipped
    skip_note = f"  ({skipped} skipped por cuota API)" if skipped else ""
    print("=" * 56)
    print(f"Resultado: {passed}/{total} passed{skip_note}", end="")
    print(f"  ({failed} failed)" if failed else "  OK todos pasaron")
    print("=" * 56)

    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
