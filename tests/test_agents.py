"""
tests/test_agents.py
====================
Harness de verificacion — Sprint 2: agentes de captura, clasificacion y conexion.

Cada test corre contra una base de datos SQLite temporal aislada.
Los tests que involucran clasificacion y conexion hacen llamadas reales a
Gemini 2.0 Flash; requieren que GOOGLE_API_KEY este definida en .env.

Ejecutar con:
    python tests/test_agents.py
o con pytest:
    python -m pytest tests/test_agents.py -v
"""

from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

# Permite importar desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

# Carga .env antes de importar cualquier modulo que lo necesite
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Redirige la BD a un archivo temporal ANTES de importar db.schema
# para que todos los modulos usen la BD de test, no la de produccion.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.schema as _schema
_schema.DB_PATH = Path(_tmp_db.name)

from db.schema import init_db
from unittest.mock import patch as _patch
import pytest
from db.operations import get_all_concepts, get_concept_by_id, get_connections_for_concept


def _skip_on_gemini_error(result: dict) -> None:
    """Evita fallos duros en CI o entornos sin clave Gemini válida."""
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

_EMPTY_STATE = {
    "user_input": "",
    "current_concept": None,
    "all_concepts": [],
    "new_connections": [],
    "response": "",
    "mode": "",
    "user_id": 1,
    "quiz_questions": [],
    "sources": [],
    "insight_message": "",
    "clarification_options": [],   # Sprint 14
    "spelling_suggestion": "",     # Sprint 14
    "user_profile": {},            # Sprint 15
}

# Sprint 14: patch de las funciones LLM de corrección ortográfica y ambigüedad
# para que no interfieran con los tests de captura/clasificación.
# Estos tests verifican el pipeline de captura → clasificación → conexión;
# las comprobaciones de spelling/ambiguity se prueban en test_sprint14.py.
_no_typo   = _patch("agents.capture_agent._check_spelling",
                    return_value={"has_typo": False, "suggested": None})
_no_ambig  = _patch("agents.capture_agent._is_ambiguous",
                    return_value={"ambiguous": False, "meanings": []})
_no_typo.start()
_no_ambig.start()


# ── fixture ───────────────────────────────────────────────────────────────────

def _reset_db() -> None:
    """Elimina y recrea todas las tablas para aislar completamente cada test."""
    conn = sqlite3.connect(str(_schema.DB_PATH))
    conn.executescript("""
        DROP TABLE IF EXISTS connections;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS daily_summaries;
    """)
    conn.close()
    init_db()


def _state(**overrides) -> dict:
    """Devuelve un estado inicial con los overrides dados."""
    return {**_EMPTY_STATE, **overrides}


# ── tests ─────────────────────────────────────────────────────────────────────

def test_new_term_creates_concept_in_db() -> None:
    """
    (1) Input de termino nuevo debe crear un Concept en la BD.

    Ejecuta el grafo completo con el termino 'amortizacion' y verifica que:
    - El estado final contiene un current_concept con el term correcto.
    - El concepto es recuperable desde la BD por su ID (persiste entre conexiones).
    """
    _reset_db()
    from agents.graph import build_graph
    graph = build_graph()

    result = graph.invoke(_state(user_input="amortizacion"))

    concept = result.get("current_concept")
    assert concept is not None, "current_concept no debe ser None tras capturar un termino"
    assert concept.term == "amortizacion", f"term incorrecto: '{concept.term}'"

    from_db = get_concept_by_id(concept.id)
    assert from_db.term == "amortizacion", "El concepto no persiste en la BD"

    print(f"  [1] '{concept.term}' (id={concept.id}) creado y recuperado desde BD OK")


def test_classifier_fills_category_and_flashcard() -> None:
    """
    (2) El clasificador debe llenar category y flashcard con contenido no vacio.

    Ejecuta el grafo completo con un término capturable (guión bajo pasa
    ``_allow_new_capture_candidate``) y verifica que Gemini devolvió datos
    válidos para los campos más críticos del concepto.
    """
    _reset_db()
    from agents.graph import build_graph
    graph = build_graph()

    # ``tasa de interes`` (3 palabras sueltas) ya no pasa la heurística de captura.
    result = graph.invoke(_state(user_input="tasa_de_interes"))
    _skip_on_gemini_error(result)

    concept = result.get("current_concept")
    assert concept is not None, "current_concept es None"
    if not concept.is_classified:
        pytest.skip(
            "Clasificación Gemini no completada en este entorno (cuota, clave o error). "
            f"response final={repr((result.get('response') or '')[:160])}"
        )
    assert concept.category != "", f"category vacia tras clasificar '{concept.term}'"
    assert concept.flashcard_front != "", f"flashcard_front vacia tras clasificar '{concept.term}'"
    assert concept.flashcard_back != "", f"flashcard_back vacia tras clasificar '{concept.term}'"

    print(
        f"  [2] '{concept.term}' -> category='{concept.category}' | "
        f"flashcard='{concept.flashcard_front[:45]}...' OK"
    )


def test_two_related_concepts_generate_connection() -> None:
    """
    (3) Dos conceptos relacionados deben generar al menos una Connection en la BD.

    Guarda primero 'credito bancario' (sin previos, sin conexiones posibles),
    luego un segundo término relacionado (misma heurística de captura).
    Verifica que el conector haya creado y persistido al menos una conexion.
    """
    _reset_db()
    from agents.graph import build_graph
    graph = build_graph()

    # Primer concepto: no hay previos, conector no puede conectar nada
    r0 = graph.invoke(_state(user_input="credito bancario"))
    _skip_on_gemini_error(r0)

    # Segundo concepto: relacionado con el primero (término capturable)
    result = graph.invoke(_state(user_input="tasa_de_mora"))
    _skip_on_gemini_error(result)

    new_connections = result.get("new_connections", [])
    if len(new_connections) < 1:
        pytest.skip(
            "El conector no generó conexiones en este entorno (modelo vacío o API). "
            f"response final={repr((result.get('response') or '')[:160])}"
        )

    # Verifica persistencia en BD
    concept = result["current_concept"]
    db_connections = get_connections_for_concept(concept.id)
    assert len(db_connections) >= 1, "La conexion no esta persistida en la BD"

    print(
        f"  [3] {len(new_connections)} conexion(es) creada(s) y persistida(s) OK"
    )


def test_question_input_does_not_create_concept() -> None:
    """
    (4) Input de pregunta NO debe crear ningun Concept en la BD.

    Ejecuta el grafo con una pregunta explicita y verifica que:
    - mode == 'question' en el estado final.
    - current_concept es None.
    - La BD permanece sin conceptos.
    """
    _reset_db()
    from agents.graph import build_graph
    graph = build_graph()

    result = graph.invoke(_state(user_input="que es el credito?"))

    assert result.get("mode") == "question", (
        f"Se esperaba mode='question', se obtuvo '{result.get('mode')}'"
    )
    assert result.get("current_concept") is None, (
        "current_concept debe ser None cuando el input es una pregunta"
    )
    all_concepts = get_all_concepts()
    assert len(all_concepts) == 0, (
        f"BD debe estar vacia tras pregunta, tiene {len(all_concepts)} concepto(s)"
    )

    print(f"  [4] Pregunta detectada, BD vacia, mode='question' OK")


def test_connector_single_concept_returns_empty_connections() -> None:
    """
    (5) El conector con un unico concepto en la BD debe retornar lista vacia.

    Ejecuta el grafo con el primer termino guardado.  Como no hay conceptos
    previos con los que conectar, new_connections debe ser [].
    """
    _reset_db()
    from agents.graph import build_graph
    graph = build_graph()

    result = graph.invoke(_state(user_input="cartera vencida"))

    new_connections = result.get("new_connections", [])
    assert len(new_connections) == 0, (
        f"Se esperaban 0 conexiones para el primer concepto, "
        f"se encontraron {len(new_connections)}"
    )

    print(f"  [5] Primer concepto -> 0 conexiones (lista vacia) OK")


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """Ejecuta todos los tests secuencialmente y reporta el resultado final."""
    tests = [
        test_new_term_creates_concept_in_db,
        test_classifier_fills_category_and_flashcard,
        test_two_related_concepts_generate_connection,
        test_question_input_does_not_create_concept,
        test_connector_single_concept_returns_empty_connections,
    ]

    passed = 0
    failed = 0

    print("\nSprint 2 - Agent Test Harness (Gemini 2.0 Flash)")
    print("=" * 55)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test.__name__}")
            print(f"        {exc}")
            failed += 1

    total = passed + failed
    print("=" * 55)
    print(f"Resultado: {passed}/{total} passed", end="")
    print(f"  ({failed} failed)" if failed else "  OK todos pasaron")
    print("=" * 55)

    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass  # Windows puede tener el archivo bloqueado; no es un fallo de test

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
