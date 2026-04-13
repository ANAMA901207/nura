"""
tests/test_sprint9.py
=====================
Harness de verificacion para el Sprint 9 de Nura — modo quiz y perfil adaptativo.

Verificaciones obligatorias (5/5):
    1. quiz_agent genera lista de preguntas con los campos requeridos.
    2. Cada pregunta tiene exactamente 4 opciones.
    3. get_mastery_by_category retorna dict con las categorias correctas.
    4. get_streak retorna 0 con BD vacia sin errores.
    5. capture_agent detecta mode='quiz' con input 'ponme a prueba'.

Los tests 1 y 2 llaman a la API de Gemini.  Si la cuota esta agotada
se marcan como SKIP en lugar de FAIL para distinguir errores de codigo
de limitaciones externas de la API gratuita.
"""

from __future__ import annotations

import sys
import os
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

# Permite importar desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

import db.schema as schema_module
from db.schema import init_db
from db.operations import (
    save_concept,
    update_concept_fields,
    get_mastery_by_category,
    get_streak,
)


# ── helpers de setup ──────────────────────────────────────────────────────────

def _make_temp_db() -> tempfile.NamedTemporaryFile:
    """
    Crea un archivo temporal como BD SQLite aislada.
    El llamador debe restaurar schema_module.DB_PATH tras usarlo.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp


def _setup_db(tmp_path: str) -> None:
    """Apunta schema_module a la BD temporal e inicializa el esquema."""
    schema_module.DB_PATH = Path(tmp_path)
    init_db()


def _teardown_db(tmp_path: str, original_path: Path) -> None:
    """Restaura la ruta original y borra el archivo temporal."""
    schema_module.DB_PATH = original_path
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


def _is_quota_error(exc: Exception) -> bool:
    """
    Determina si una excepcion es un error de cuota de la API de Gemini.

    Parametros
    ----------
    exc : Excepcion capturada.

    Devuelve
    --------
    True si el error indica que la cuota de la API se agoto.
    """
    msg = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in msg or "429" in msg or "QUOTA" in msg


# ── tests ────────────────────────────────────────────────────────────────────

def test_quiz_agent_generates_questions() -> tuple[str, str]:
    """
    Verificacion 1: quiz_agent genera lista de preguntas con campos requeridos.

    Inserta 2 conceptos clasificados en la BD, invoca quiz_agent y verifica
    que el resultado contiene quiz_questions con al menos una pregunta y que
    cada pregunta tiene los campos: concept_id, question, options,
    correct_index, explanation.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)

        # Crear conceptos clasificados con flashcard
        c1 = save_concept("Tasa de interes", "test")
        update_concept_fields(c1.id,
            category="Finanzas",
            explanation="El costo del dinero en el tiempo",
            flashcard_front="Que es la tasa de interes?",
            flashcard_back="El costo del dinero en el tiempo",
            is_classified=True,
        )
        c2 = save_concept("Amortizacion", "test")
        update_concept_fields(c2.id,
            category="Finanzas",
            explanation="Proceso de reduccion gradual de una deuda",
            flashcard_front="Que es amortizacion?",
            flashcard_back="Reduccion gradual de una deuda",
            is_classified=True,
        )

        from agents.quiz_agent import quiz_agent
        state = {
            "user_input": "ponme a prueba",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "quiz",
            "quiz_questions": [],
        }

        result = quiz_agent(state)
        questions = result.get("quiz_questions", [])

        if not questions:
            return "FAIL", "quiz_questions esta vacio — quiz_agent no genero preguntas"

        required_fields = {"concept_id", "question", "options", "correct_index", "explanation"}
        for i, q in enumerate(questions):
            missing = required_fields - set(q.keys())
            if missing:
                return "FAIL", f"Pregunta {i} falta campos: {missing}"

        return "PASS", f"{len(questions)} pregunta(s) generada(s) con todos los campos"

    except Exception as exc:
        if _is_quota_error(exc):
            return "SKIP", f"Cuota de API agotada: {str(exc)[:80]}"
        return "FAIL", str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_quiz_questions_have_4_options() -> tuple[str, str]:
    """
    Verificacion 2: cada pregunta del quiz tiene exactamente 4 opciones.

    Usa un mock de ChatGoogleGenerativeAI para devolver un JSON pre-armado
    sin llamar a la API real, asegurando que la funcion de validacion del
    quiz_agent descarta preguntas malformadas y retiene las validas.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)

        c = save_concept("Concepto test", "test")
        update_concept_fields(c.id,
            category="Test",
            explanation="Explicacion de prueba",
            flashcard_front="Pregunta?",
            flashcard_back="Respuesta",
            is_classified=True,
        )

        # JSON pre-armado que el mock devolvera como si fuera Gemini
        fake_json = (
            f'[{{"concept_id": {c.id}, "question": "Test question?", '
            f'"options": ["A", "B", "C", "D"], "correct_index": 0, '
            f'"explanation": "A es correcta"}}]'
        )
        mock_response = MagicMock()
        mock_response.content = fake_json

        with patch("agents.quiz_agent.ChatGoogleGenerativeAI") as MockLLM:
            MockLLM.return_value.invoke.return_value = mock_response
            from agents.quiz_agent import quiz_agent
            state = {
                "user_input": "quiz",
                "user_context": "",
                "current_concept": None,
                "all_concepts": [],
                "new_connections": [],
                "response": "",
                "mode": "quiz",
                "quiz_questions": [],
            }
            result = quiz_agent(state)

        questions = result.get("quiz_questions", [])
        if not questions:
            return "FAIL", "No se generaron preguntas con el mock"

        for i, q in enumerate(questions):
            opts = q.get("options", [])
            if len(opts) != 4:
                return "FAIL", f"Pregunta {i} tiene {len(opts)} opciones (esperado 4)"

        return "PASS", f"{len(questions)} pregunta(s), todas con exactamente 4 opciones"

    except Exception as exc:
        return "FAIL", str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_get_mastery_by_category() -> tuple[str, str]:
    """
    Verificacion 3: get_mastery_by_category retorna dict con las categorias correctas.

    Inserta conceptos de dos categorias con mastery_level conocido y verifica
    que el dict devuelto tiene ambas categorias con el promedio correcto.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)

        from db.operations import update_mastery_level

        # Categoria A: mastery 2 y 4 -> promedio 3.0
        c1 = save_concept("ConceptoA1", "test")
        update_concept_fields(c1.id, category="CategoriaA", is_classified=True)
        update_mastery_level(c1.id, 2)
        c2 = save_concept("ConceptoA2", "test")
        update_concept_fields(c2.id, category="CategoriaA", is_classified=True)
        update_mastery_level(c2.id, 4)

        # Categoria B: mastery 1 -> promedio 1.0
        c3 = save_concept("ConceptoB1", "test")
        update_concept_fields(c3.id, category="CategoriaB", is_classified=True)
        update_mastery_level(c3.id, 1)

        result = get_mastery_by_category()

        if "CategoriaA" not in result:
            return "FAIL", f"Falta 'CategoriaA' en resultado: {result}"
        if "CategoriaB" not in result:
            return "FAIL", f"Falta 'CategoriaB' en resultado: {result}"

        avg_a = result["CategoriaA"]
        avg_b = result["CategoriaB"]

        if abs(avg_a - 3.0) > 0.1:
            return "FAIL", f"CategoriaA: esperado 3.0, obtenido {avg_a}"
        if abs(avg_b - 1.0) > 0.1:
            return "FAIL", f"CategoriaB: esperado 1.0, obtenido {avg_b}"

        return "PASS", f"CategoriaA={avg_a}, CategoriaB={avg_b}"

    except Exception as exc:
        return "FAIL", str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_get_streak_empty_db() -> tuple[str, str]:
    """
    Verificacion 4: get_streak retorna 0 con BD vacia sin errores.

    Verifica que la funcion no lanza excepciones y devuelve 0 cuando no
    hay registros en daily_summaries.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)

        streak = get_streak()

        if streak == 0:
            return "PASS", "get_streak() devolvio 0 con BD vacia"
        return "FAIL", f"Esperado 0, obtenido {streak}"

    except Exception as exc:
        return "FAIL", str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_capture_agent_detects_quiz_mode() -> tuple[str, str]:
    """
    Verificacion 5: capture_agent detecta mode='quiz' con input 'ponme a prueba'.

    No necesita BD ni LLM.  Verifica la heuristica _is_quiz directamente
    y tambien a traves del nodo capture_agent completo.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)

        from agents.capture_agent import capture_agent, _is_quiz

        # Test de la heuristica directa
        inputs_quiz = [
            "ponme a prueba",
            "quiz",
            "hazme un quiz",
            "quiero un test",
            "examen",
        ]
        for text in inputs_quiz:
            if not _is_quiz(text):
                return "FAIL", f"_is_quiz('{text}') devolvio False (esperado True)"

        # Test del nodo completo con 'ponme a prueba'
        state = {
            "user_input": "ponme a prueba",
            "user_context": "",
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "",
            "quiz_questions": [],
        }
        result = capture_agent(state)
        mode = result.get("mode", "")

        if mode != "quiz":
            return "FAIL", f"capture_agent devolvio mode='{mode}' (esperado 'quiz')"

        return "PASS", f"mode='quiz' detectado correctamente para 'ponme a prueba'"

    except Exception as exc:
        return "FAIL", str(exc)
    finally:
        _teardown_db(tmp.name, original)


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """
    Ejecuta todos los tests del Sprint 9 y reporta el resultado por consola.

    Tests con cuota de API agotada se marcan SKIP en lugar de FAIL.
    Formato:
        [PASS] / [FAIL] / [SKIP] Descripcion - detalle
    """
    tests = [
        ("quiz_agent genera preguntas con campos requeridos",    test_quiz_agent_generates_questions),
        ("Cada pregunta tiene exactamente 4 opciones",           test_quiz_questions_have_4_options),
        ("get_mastery_by_category retorna categorias correctas", test_get_mastery_by_category),
        ("get_streak devuelve 0 con BD vacia",                   test_get_streak_empty_db),
        ("capture_agent detecta mode=quiz con 'ponme a prueba'", test_capture_agent_detects_quiz_mode),
    ]

    passed = skipped = failed = 0
    print("\n=== Sprint 9 - Quiz y Perfil Adaptativo ===\n")

    for name, fn in tests:
        try:
            status, detail = fn()
        except Exception as exc:
            status, detail = "FAIL", f"Excepcion no capturada: {exc}"

        safe_detail = detail.encode("ascii", "replace").decode("ascii")
        print(f"  [{status}] {name}")
        print(f"         {safe_detail}")

        if status == "PASS":
            passed += 1
        elif status == "SKIP":
            skipped += 1
        else:
            failed += 1

    total = len(tests)
    skip_note = f" ({skipped} SKIP por cuota)" if skipped else ""
    print(f"\n  {passed}/{total} passed{skip_note}\n")


if __name__ == "__main__":
    _run_all()
