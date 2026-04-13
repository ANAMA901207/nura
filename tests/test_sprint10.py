"""
tests/test_sprint10.py
======================
Harness de verificacion para el Sprint 10 de Nura — tutor con web search.

Verificaciones obligatorias (5/5):
    1. Pregunta sobre version de herramienta retorna needs_search=True.
    2. Pregunta conceptual simple retorna needs_search=False.
    3. web_search con query valida retorna dict con campo results.
    4. Fallo de web_search retorna dict con results vacio sin lanzar excepcion.
    5. Tutor responde correctamente cuando web_search retorna vacio (fallback a BD).

Los tests 1 y 2 llaman a la API de Gemini para la clasificacion.
Se marcan SKIP si la cuota esta agotada.
Los tests 3 y 4 usan la red real (DuckDuckGo) o mocks segun disponibilidad.
El test 5 usa mock completo para no consumir cuota.
"""

from __future__ import annotations

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Permite importar desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

import db.schema as schema_module
from db.schema import init_db
from db.operations import save_concept, update_concept_fields


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
    Determina si una excepcion corresponde a cuota de API agotada.

    Parametros
    ----------
    exc : Excepcion capturada.

    Devuelve
    --------
    True si el error indica cuota de Gemini o rate limit.
    """
    msg = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in msg or "429" in msg or "QUOTA" in msg


# ── tests ────────────────────────────────────────────────────────────────────

def test_needs_search_true_for_tool_version() -> tuple[str, str]:
    """
    Verificacion 1: pregunta sobre version de herramienta retorna needs_search=True.

    Llama a Gemini con el clasificador de tutor_agent y verifica que una
    pregunta sobre una version especifica de software activa needs_search=True.
    Usa la API real — se marca SKIP si la cuota esta agotada.
    """
    try:
        from agents.tutor_agent import _call_gemini, _parse_needs_search, CLASSIFY_SYSTEM_PROMPT
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return "SKIP", "GOOGLE_API_KEY no definida"

        llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            google_api_key=api_key,  # type: ignore[call-arg]
            temperature=0.0,
        )
        question = "que version de LangChain es la mas reciente?"
        raw = _call_gemini(
            llm,
            [
                SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
                HumanMessage(content=f"question: {question}"),
            ],
        )
        result = _parse_needs_search(raw)

        if result is True:
            return "PASS", f"needs_search=True para '{question}'"
        return "FAIL", f"needs_search={result} (esperado True) — raw: {raw[:80]}"

    except Exception as exc:
        if _is_quota_error(exc):
            return "SKIP", f"Cuota agotada: {str(exc)[:80]}"
        return "FAIL", str(exc)


def test_needs_search_false_for_conceptual() -> tuple[str, str]:
    """
    Verificacion 2: pregunta conceptual simple retorna needs_search=False.

    Verifica que el clasificador distingue preguntas conceptuales (que no
    necesitan informacion actualizada) de preguntas sobre herramientas.
    Usa la API real — se marca SKIP si la cuota esta agotada.
    """
    try:
        from agents.tutor_agent import _call_gemini, _parse_needs_search, CLASSIFY_SYSTEM_PROMPT
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return "SKIP", "GOOGLE_API_KEY no definida"

        llm = ChatGoogleGenerativeAI(
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            google_api_key=api_key,  # type: ignore[call-arg]
            temperature=0.0,
        )
        question = "que es la tasa de interes?"
        raw = _call_gemini(
            llm,
            [
                SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
                HumanMessage(content=f"question: {question}"),
            ],
        )
        result = _parse_needs_search(raw)

        if result is False:
            return "PASS", f"needs_search=False para '{question}'"
        return "FAIL", f"needs_search={result} (esperado False) — raw: {raw[:80]}"

    except Exception as exc:
        if _is_quota_error(exc):
            return "SKIP", f"Cuota agotada: {str(exc)[:80]}"
        return "FAIL", str(exc)


def test_web_search_returns_results_dict() -> tuple[str, str]:
    """
    Verificacion 3: web_search con query valida retorna dict con campo results.

    Verifica que la funcion devuelve un dict con la clave 'results' (puede
    ser lista vacia si la red falla, pero la estructura debe ser correcta).
    No lanza excepciones en ningun caso.
    """
    try:
        from tools.search_tool import web_search

        result = web_search("Python programming language")

        if not isinstance(result, dict):
            return "FAIL", f"Se esperaba dict, obtenido {type(result)}"

        if "results" not in result:
            return "FAIL", f"Falta campo 'results' en: {list(result.keys())}"

        if not isinstance(result["results"], list):
            return "FAIL", f"'results' debe ser list, es {type(result['results'])}"

        # Si hay resultados, verificar estructura de cada uno
        for i, r in enumerate(result["results"][:3]):
            for field in ("title", "url", "snippet"):
                if field not in r:
                    return "FAIL", f"Resultado {i} falta campo '{field}'"

        n = len(result["results"])
        return "PASS", f"dict valido con {n} resultado(s)"

    except Exception as exc:
        return "FAIL", str(exc)


def test_web_search_failure_returns_empty_no_exception() -> tuple[str, str]:
    """
    Verificacion 4: fallo de web_search retorna dict con results vacio sin excepcion.

    Usa mock para simular un fallo en DDGS.text y verifica que web_search
    captura el error y devuelve {"results": [], "error": str} en lugar de
    propagar la excepcion.
    """
    try:
        from tools.search_tool import web_search

        with patch("tools.search_tool.DDGS") as MockDDGS:
            instance = MockDDGS.return_value.__enter__.return_value
            instance.text.side_effect = Exception("Connection refused (mock)")
            result = web_search("test query")

        if not isinstance(result, dict):
            return "FAIL", f"Se esperaba dict, obtenido {type(result)}"

        if result.get("results") != []:
            return "FAIL", f"'results' debe ser [] en caso de error, obtenido: {result.get('results')}"

        if "error" not in result:
            return "FAIL", "Falta campo 'error' cuando la busqueda falla"

        error_msg = result["error"]
        return "PASS", f"results=[], error='{error_msg[:60]}'"

    except Exception as exc:
        return "FAIL", f"web_search propago excepcion: {exc}"


def test_tutor_fallback_when_search_empty() -> tuple[str, str]:
    """
    Verificacion 5: tutor responde correctamente con web_search vacio (fallback a BD).

    Usa mocks para:
    - Forzar que _classify_needs_search devuelva needs_search=True
    - Forzar que web_search devuelva {"results": []} (sin resultados)
    - Simular la respuesta final de Gemini con texto predefinido

    Verifica que tutor_agent devuelve response no vacia y sources=[].
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)

        # Respuesta mock de Gemini para el clasificador y para el tutor
        mock_classify = MagicMock()
        mock_classify.content = '{"needs_search": true}'

        mock_tutor_resp = MagicMock()
        mock_tutor_resp.content = "Esta es la respuesta del tutor con contexto de BD."

        call_count = [0]

        def fake_invoke(messages):
            call_count[0] += 1
            # Primera llamada = clasificador, segunda = tutor
            if call_count[0] == 1:
                return mock_classify
            return mock_tutor_resp

        with patch("agents.tutor_agent.ChatGoogleGenerativeAI") as MockLLM, \
             patch("agents.tutor_agent.web_search") as mock_search:

            MockLLM.return_value.invoke.side_effect = fake_invoke
            mock_search.return_value = {"results": []}  # busqueda vacia

            from agents.tutor_agent import tutor_agent

            with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key-for-test"}):
                state = {
                    "user_input": "que es la tasa de interes?",
                    "user_context": "",
                    "current_concept": None,
                    "all_concepts": [],
                    "new_connections": [],
                    "response": "",
                    "mode": "question",
                    "quiz_questions": [],
                    "sources": [],
                }
                result = tutor_agent(state)

        response = result.get("response", "")
        sources = result.get("sources", [])

        if not response:
            return "FAIL", "response esta vacia — el tutor no respondio"
        if sources:
            return "FAIL", f"sources debe ser [] con busqueda vacia, obtenido: {sources}"

        return "PASS", f"response={response[:60]}..., sources=[]"

    except Exception as exc:
        return "FAIL", str(exc)
    finally:
        _teardown_db(tmp.name, original)


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """
    Ejecuta todos los tests del Sprint 10 y reporta el resultado por consola.

    Tests que llaman a la API de Gemini se marcan SKIP si la cuota esta agotada.
    Formato de salida:
        [PASS] / [FAIL] / [SKIP] Descripcion - detalle
    """
    tests = [
        ("Pregunta de version activa needs_search=True",          test_needs_search_true_for_tool_version),
        ("Pregunta conceptual activa needs_search=False",         test_needs_search_false_for_conceptual),
        ("web_search devuelve dict con campo results",            test_web_search_returns_results_dict),
        ("Fallo de web_search no lanza excepcion",               test_web_search_failure_returns_empty_no_exception),
        ("Tutor usa fallback a BD si web_search esta vacio",     test_tutor_fallback_when_search_empty),
    ]

    passed = skipped = failed = 0
    print("\n=== Sprint 10 - Tutor con Web Search ===\n")

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
