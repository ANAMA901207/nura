"""
tests/test_sprint6.py
=====================
Harness de verificación — Sprint 6: Mapa interactivo con filtros y panel de detalle.

Todos los tests son deterministas (sin llamadas a la API de Gemini).

Ejecutar con:
    python tests/test_sprint6.py
"""

from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# BD temporal aislada
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.schema as _schema
_schema.DB_PATH = Path(_tmp_db.name)

from db.schema import init_db
from db.operations import (
    save_concept,
    save_connection,
    update_concept_fields,
    get_concept_connections_detail,
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


def _make_concept(term: str, category: str = "", mastery: int = 0) -> object:
    """Crea un concepto de prueba con categoría y mastery opcionales."""
    c = save_concept(term=term, context="test")
    if category or mastery:
        c = update_concept_fields(
            c.id,
            category=category,
            is_classified=1 if category else 0,
            explanation=f"Explicacion de {term}.",
        )
        if mastery:
            from db.operations import update_mastery_level
            c = update_mastery_level(c.id, mastery)
    return c


# ── tests ─────────────────────────────────────────────────────────────────────

def test_get_concept_connections_detail_returns_correct_fields() -> None:
    """
    (1) get_concept_connections_detail retorna dicts con campos 'concept' y 'relationship'.

    Crea dos conceptos conectados, llama a get_concept_connections_detail
    para el primero y verifica que cada elemento tiene exactamente las claves
    'concept' y 'relationship', y que el concepto devuelto es el del otro extremo.
    """
    _reset_db()
    c1 = _make_concept("LangGraph", "Tecnologia")
    c2 = _make_concept("OpenRouter", "Tecnologia")
    save_connection(c1.id, c2.id, relationship="son herramientas de orquestacion de LLMs")

    detail = get_concept_connections_detail(c1.id)

    assert len(detail) == 1, f"Se esperaba 1 conexion, se obtuvo {len(detail)}"
    item = detail[0]
    assert "concept" in item, "El dict debe tener la clave 'concept'"
    assert "relationship" in item, "El dict debe tener la clave 'relationship'"
    assert item["concept"].id == c2.id, (
        f"El concepto del otro extremo debe ser c2 (id={c2.id}), "
        f"se obtuvo id={item['concept'].id}"
    )
    assert "orquestacion" in item["relationship"].lower(), (
        "El relationship debe contener el texto de la relacion guardada"
    )

    print("  [1] get_concept_connections_detail retorna dicts con concept y relationship: OK")


def test_filter_by_category_reduces_visible_nodes() -> None:
    """
    (2) El filtro por categoría reduce correctamente los conceptos del grafo.

    Crea conceptos de dos categorías distintas, llama a render_knowledge_map
    con filter_categories limitando a una sola categoría, y verifica que el
    HTML generado no contiene los términos de la otra categoría como nodos.
    """
    _reset_db()
    _make_concept("tasa_interes", "Finanzas")
    _make_concept("amortizacion", "Finanzas")
    _make_concept("algoritmo", "Tecnologia")

    # Mockea streamlit para que no bloquee
    from unittest.mock import MagicMock
    sys.modules.setdefault("streamlit", MagicMock())

    if "ui.components" in sys.modules:
        del sys.modules["ui.components"]

    from db.operations import get_all_concepts, get_all_connections
    from ui.components import render_knowledge_map

    all_concepts = get_all_concepts()
    all_connections = get_all_connections()

    # Solo mostrar Finanzas
    html = render_knowledge_map(
        all_concepts, all_connections,
        filter_categories=["Finanzas"],
    )

    assert "tasa_interes" in html, "El nodo de Finanzas debe estar en el mapa"
    assert "amortizacion" in html, "El nodo de Finanzas debe estar en el mapa"
    assert "algoritmo" not in html, (
        "El nodo de Tecnologia debe estar excluido al filtrar solo Finanzas"
    )

    print("  [2] Filtro por categoria reduce nodos visibles correctamente: OK")


def test_filter_by_min_mastery_excludes_low_mastery() -> None:
    """
    (3) El filtro por dominio mínimo excluye conceptos con mastery menor al umbral.

    Crea conceptos con distintos niveles de dominio, aplica filter_min_mastery=3
    y verifica que los conceptos con mastery < 3 no aparecen en el HTML.
    """
    _reset_db()
    c_low  = _make_concept("concepto_basico",   "Finanzas", mastery=1)
    c_mid  = _make_concept("concepto_medio",    "Finanzas", mastery=3)
    c_high = _make_concept("concepto_avanzado", "Finanzas", mastery=5)

    if "ui.components" in sys.modules:
        del sys.modules["ui.components"]

    from db.operations import get_all_concepts, get_all_connections
    from ui.components import render_knowledge_map

    all_concepts = get_all_concepts()
    all_connections = get_all_connections()

    html = render_knowledge_map(
        all_concepts, all_connections,
        filter_min_mastery=3,
    )

    assert c_low.term not in html, (
        f"'{c_low.term}' (mastery=1) debe estar excluido con filter_min_mastery=3"
    )
    assert c_mid.term in html, (
        f"'{c_mid.term}' (mastery=3) debe aparecer con filter_min_mastery=3"
    )
    assert c_high.term in html, (
        f"'{c_high.term}' (mastery=5) debe aparecer con filter_min_mastery=3"
    )

    print("  [3] Filtro por dominio minimo excluye conceptos con mastery insuficiente: OK")


def test_render_concept_detail_panel_no_error_without_connections() -> None:
    """
    (4) render_concept_detail_panel no lanza error con un concepto sin conexiones.

    Crea un concepto sin ninguna conexión y llama a render_concept_detail_panel
    con lista de conexiones vacía.  Verifica que no se lanza ninguna excepción.
    """
    _reset_db()
    concept = _make_concept("concepto_solitario", "Finanzas")

    from unittest.mock import MagicMock

    # Guardar el mock activo para restaurarlo al salir
    _prev_st = sys.modules.get("streamlit")
    mock_st = MagicMock()
    mock_st.expander.return_value.__enter__ = lambda s: s
    mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
    sys.modules["streamlit"] = mock_st

    if "ui.components" in sys.modules:
        del sys.modules["ui.components"]

    try:
        from ui.components import render_concept_detail_panel
        render_concept_detail_panel(concept, connections_detail=[])

        # Verificar que llamó a st.markdown al menos una vez (cabecera del panel)
        assert mock_st.markdown.called, "Debe llamar a st.markdown al menos una vez"
    except AssertionError:
        raise
    except Exception as exc:
        raise AssertionError(
            f"render_concept_detail_panel lanzó error con lista vacía: {exc}"
        )
    finally:
        # Restaurar el mock anterior para no contaminar tests posteriores
        if _prev_st is not None:
            sys.modules["streamlit"] = _prev_st
        else:
            sys.modules.pop("streamlit", None)
        if "ui.components" in sys.modules:
            del sys.modules["ui.components"]

    print("  [4] render_concept_detail_panel no lanza error sin conexiones: OK")


def test_render_knowledge_map_empty_concepts_no_error() -> None:
    """
    (5) render_knowledge_map con lista vacía de conceptos no lanza error.

    Caso edge: la BD está vacía o todos los conceptos fueron filtrados.
    El HTML resultante debe ser una cadena válida (no None, no excepción).
    """
    _reset_db()

    from unittest.mock import MagicMock
    sys.modules.setdefault("streamlit", MagicMock())

    if "ui.components" in sys.modules:
        del sys.modules["ui.components"]

    from ui.components import render_knowledge_map

    try:
        html = render_knowledge_map([], [])
    except Exception as exc:
        raise AssertionError(
            f"render_knowledge_map lanzó error con lista vacía: {exc}"
        )

    assert isinstance(html, str) and len(html) > 0, (
        "render_knowledge_map debe retornar un str no vacío incluso sin conceptos"
    )

    print("  [5] render_knowledge_map con lista vacia no lanza error: OK")


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """Ejecuta todos los tests y reporta el resultado final."""
    tests = [
        test_get_concept_connections_detail_returns_correct_fields,
        test_filter_by_category_reduces_visible_nodes,
        test_filter_by_min_mastery_excludes_low_mastery,
        test_render_concept_detail_panel_no_error_without_connections,
        test_render_knowledge_map_empty_concepts_no_error,
    ]

    passed = 0
    failed = 0

    print("\nSprint 6 - Mapa interactivo + Filtros - Test Harness")
    print("=" * 54)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test.__name__}")
            print(f"        {exc}")
            import traceback
            traceback.print_exc()
            failed += 1

    total = passed + failed
    print("=" * 54)
    print(f"Resultado: {passed}/{total} passed", end="")
    print(f"  ({failed} failed)" if failed else "  OK todos pasaron")
    print("=" * 54)

    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
