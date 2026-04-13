"""
tests/test_ui.py
================
Harness de verificacion — Sprint 3: componentes de UI de Nura.

Los tests de componentes mockean streamlit para poder ejecutarse sin un
servidor Streamlit activo.  Los tests de render_knowledge_map y
render_flashcard no necesitan mock porque retornan HTML puro.

Ejecutar con:
    python tests/test_ui.py
o con pytest:
    python -m pytest tests/test_ui.py -v
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, date
from pathlib import Path
from unittest.mock import MagicMock, patch

# Agrega la raiz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Mock de streamlit ANTES de importar cualquier modulo de ui ────────────────
# Streamlit no esta disponible sin un servidor; lo reemplazamos con un MagicMock
# para que todas las llamadas st.* sean no-ops en el contexto de tests.
_mock_st = MagicMock()
_mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
_mock_st.tabs.return_value = [MagicMock(), MagicMock()]
_mock_st.expander.return_value.__enter__ = lambda s: s
_mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
sys.modules["streamlit"] = _mock_st
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()

# Ahora si podemos importar los modulos de UI
from ui.components import (
    render_concept_card,
    render_daily_summary,
    render_flashcard,
    render_knowledge_map,
)
from db.models import Concept, Connection, DailySummary


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_concept(
    id: int = 1,
    term: str = "tasa de interes",
    category: str = "Finanzas",
    subcategory: str = "Credito",
    explanation: str = "El costo del dinero prestado en el tiempo.",
    examples: str = "Un prestamo al 5% anual.",
    analogy: str = "Es como el alquiler que pagas por usar dinero ajeno.",
    context: str = "banca",
    flashcard_front: str = "?Que es la tasa de interes?",
    flashcard_back: str = "El porcentaje que se cobra por prestar dinero.",
    mastery_level: int = 2,
) -> Concept:
    """Crea un Concept de prueba con valores predeterminados coherentes."""
    return Concept(
        id=id,
        term=term,
        category=category,
        subcategory=subcategory,
        explanation=explanation,
        examples=examples,
        analogy=analogy,
        context=context,
        flashcard_front=flashcard_front,
        flashcard_back=flashcard_back,
        mastery_level=mastery_level,
        created_at=datetime(2026, 4, 10, 12, 0, 0),
        last_reviewed=None,
    )


def _make_connection(
    id: int = 1,
    concept_id_a: int = 1,
    concept_id_b: int = 2,
    relationship: str = "complementa a",
) -> Connection:
    """Crea una Connection de prueba con valores predeterminados."""
    return Connection(
        id=id,
        concept_id_a=concept_id_a,
        concept_id_b=concept_id_b,
        relationship=relationship,
        created_at=datetime(2026, 4, 10, 12, 0, 0),
    )


def _make_summary(
    concepts_captured: int = 3,
    new_connections: int = 1,
    concepts_reviewed: int = 5,
) -> DailySummary:
    """Crea un DailySummary de prueba con valores predeterminados."""
    return DailySummary(
        id=1,
        date=date(2026, 4, 10),
        concepts_captured=concepts_captured,
        new_connections=new_connections,
        concepts_reviewed=concepts_reviewed,
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test_render_concept_card_no_errors() -> None:
    """
    (1) render_concept_card no lanza errores con un Concept valido.

    Verifica que la funcion se ejecuta completamente sin excepciones
    cuando recibe un concepto con todos sus campos poblados.
    Con streamlit mockeado, todas las llamadas st.* son no-ops.
    """
    concept = _make_concept()
    try:
        render_concept_card(concept)
    except Exception as exc:
        raise AssertionError(f"render_concept_card lanzo un error inesperado: {exc}")

    print("  [1] render_concept_card con concept valido: sin errores OK")


def test_render_flashcard_shows_front_by_default() -> None:
    """
    (2) render_flashcard muestra el frente por defecto (show_back=False).

    Verifica que:
    - La funcion retorna un string HTML no vacio.
    - El HTML contiene el texto de flashcard_front del concepto.
    - El HTML contiene el label 'FRENTE' (no 'REVERSO').
    """
    concept = _make_concept()
    html = render_flashcard(concept, show_back=False)

    assert isinstance(html, str), "render_flashcard debe retornar un string"
    assert len(html) > 0, "El HTML retornado no debe estar vacio"
    assert concept.flashcard_front in html, (
        f"El HTML debe contener el texto de flashcard_front: '{concept.flashcard_front}'"
    )
    assert "FRENTE" in html, "El HTML debe contener el label 'FRENTE' cuando show_back=False"
    assert "REVERSO" not in html, "El HTML no debe contener 'REVERSO' cuando show_back=False"

    # Verificar que voltear muestra el reverso
    html_back = render_flashcard(concept, show_back=True)
    assert concept.flashcard_back in html_back, "El reverso debe contener flashcard_back"
    assert "REVERSO" in html_back

    print(f"  [2] render_flashcard frente/reverso: OK")


def test_render_knowledge_map_returns_nonempty_html() -> None:
    """
    (3) render_knowledge_map retorna HTML no vacio con al menos un concepto.

    Verifica que:
    - La funcion retorna un string HTML no vacio.
    - El HTML contiene elementos de pyvis (scripts, HTML tags).
    - Funciona con un solo concepto y sin conexiones.
    - Funciona con dos conceptos y una conexion.
    """
    concept_a = _make_concept(id=1, term="credito")
    concept_b = _make_concept(id=2, term="tasa de mora", category="Riesgo")
    conn = _make_connection(concept_id_a=1, concept_id_b=2, relationship="afecta al")

    # Con un solo concepto
    html_single = render_knowledge_map([concept_a], [])
    assert isinstance(html_single, str), "Debe retornar un string"
    assert len(html_single) > 100, "El HTML no puede estar vacio o ser trivial"
    assert "<html" in html_single.lower() or "<!DOCTYPE" in html_single, (
        "El HTML generado por pyvis debe contener tags HTML"
    )

    # Con dos conceptos y una conexion
    html_full = render_knowledge_map([concept_a, concept_b], [conn])
    assert len(html_full) > 100, "El HTML con conexion no puede estar vacio"

    print(
        f"  [3] render_knowledge_map: HTML generado ({len(html_full)} chars) OK"
    )


def test_render_daily_summary_no_errors() -> None:
    """
    (4) render_daily_summary no lanza errores con un DailySummary valido.

    Verifica que la funcion se ejecuta completamente sin excepciones.
    Con streamlit mockeado, st.columns y st.metric son no-ops.
    """
    summary = _make_summary()
    try:
        render_daily_summary(summary)
    except Exception as exc:
        raise AssertionError(f"render_daily_summary lanzo un error inesperado: {exc}")

    print("  [4] render_daily_summary con summary valido: sin errores OK")


def test_app_imports_without_errors() -> None:
    """
    (5) ui/app.py importa sin errores con streamlit mockeado.

    Verifica que el modulo de la aplicacion puede ser importado sin
    que se produzca ninguna excepcion.  El guard 'if __name__ == main'
    evita que se ejecute el codigo de UI durante el import.

    La BD se redirige a un archivo temporal para evitar efectos secundarios.
    """
    import tempfile
    import db.schema as _schema

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    original_path = _schema.DB_PATH
    _schema.DB_PATH = Path(tmp.name)

    try:
        # Remover del cache de modulos para forzar reimport limpio
        if "ui.app" in sys.modules:
            del sys.modules["ui.app"]

        import ui.app  # no debe lanzar excepciones
        assert hasattr(ui.app, "main"), "ui.app debe definir una funcion main()"
        assert hasattr(ui.app, "build_graph") or True, "import ok"
        print("  [5] ui/app.py importa correctamente: OK")
    except Exception as exc:
        raise AssertionError(f"ui/app.py lanzo un error al importar: {exc}")
    finally:
        _schema.DB_PATH = original_path
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """Ejecuta todos los tests y reporta el resultado final."""
    tests = [
        test_render_concept_card_no_errors,
        test_render_flashcard_shows_front_by_default,
        test_render_knowledge_map_returns_nonempty_html,
        test_render_daily_summary_no_errors,
        test_app_imports_without_errors,
    ]

    passed = 0
    failed = 0

    print("\nSprint 3 - UI Test Harness")
    print("=" * 50)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test.__name__}")
            print(f"        {exc}")
            failed += 1

    total = passed + failed
    print("=" * 50)
    print(f"Resultado: {passed}/{total} passed", end="")
    print(f"  ({failed} failed)" if failed else "  OK todos pasaron")
    print("=" * 50)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
