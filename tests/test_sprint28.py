"""
tests/test_sprint28.py
======================
Harness para Sprint 28 — Árbol jerárquico conceptual.

Verifica:
1. test_hierarchy_table_exists       — tabla concept_hierarchy creada.
2. test_save_and_get_hierarchy       — guardar relación y recuperarla.
3. test_get_concept_tree_structure   — árbol tiene estructura dict anidada.
4. test_hierarchy_agent_returns_list — detect_hierarchy con mock Gemini → lista.
5. test_hierarchy_agent_empty_on_failure — Gemini falla → lista vacía.
6. test_arbol_command_returns_text   — /arbol → string no vacío.
7. test_arbol_with_category_filters  — /arbol IA → solo conceptos de IA.

Estrategia
----------
- BD: SQLite temporal aislada por test (fixture tmp_db).
- LLM: siempre mockeado; nunca se llama a Gemini desde los tests.
- Handlers: se prueban directamente (sin process_update) para test 6 y 7.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")


# ── fixture: BD aislada ───────────────────────────────────────────────────────

import db.schema as _schema
from db.schema import init_db
from db.operations import create_user, save_concept, save_hierarchy, get_hierarchy, get_concept_tree


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_nura.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def _make_concept(db_path: Path, user_id: int, term: str, category: str = "") -> int:
    """Inserta un concepto mínimo y retorna su id."""
    created_at = datetime.now().isoformat()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """INSERT OR IGNORE INTO concepts
               (term, category, subcategory, explanation, examples, analogy,
                context, flashcard_front, flashcard_back, mastery_level,
                created_at, user_id)
               VALUES (?,?,'',' ','','','','','',0,?,?)""",
            (term, category, created_at, user_id),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM concepts WHERE term=? AND user_id=?", (term, user_id)).fetchone()
        return row[0]
    finally:
        conn.close()


# ── 1. tabla concept_hierarchy existe ────────────────────────────────────────

def test_hierarchy_table_exists(tmp_db):
    """init_db() debe crear la tabla concept_hierarchy."""
    conn = sqlite3.connect(str(tmp_db))
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='concept_hierarchy'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "La tabla concept_hierarchy no fue creada por init_db()."


# ── 2. save_hierarchy + get_hierarchy ────────────────────────────────────────

def test_save_and_get_hierarchy(tmp_db):
    """Guardar una relación y recuperarla con get_hierarchy."""
    user = create_user("ana28", "pass123")
    child_id  = _make_concept(tmp_db, user.id, "Machine Learning", "IA")
    parent_id = _make_concept(tmp_db, user.id, "Inteligencia Artificial", "IA")

    save_hierarchy(user.id, child_id, parent_id, "es_tipo_de")

    rels = get_hierarchy(user.id)
    assert len(rels) == 1, f"Se esperaba 1 relación, se obtuvieron {len(rels)}."
    assert rels[0]["child_id"]      == child_id
    assert rels[0]["parent_id"]     == parent_id
    assert rels[0]["relation_type"] == "es_tipo_de"
    assert rels[0]["child_term"]    == "Machine Learning"
    assert rels[0]["parent_term"]   == "Inteligencia Artificial"


# ── 3. get_concept_tree estructura ───────────────────────────────────────────

def test_get_concept_tree_structure(tmp_db):
    """get_concept_tree retorna dict anidado con 'children'."""
    user      = create_user("bob28", "pass123")
    ml_id     = _make_concept(tmp_db, user.id, "Machine Learning", "IA")
    ia_id     = _make_concept(tmp_db, user.id, "Inteligencia Artificial", "IA")
    dl_id     = _make_concept(tmp_db, user.id, "Deep Learning", "IA")

    save_hierarchy(user.id, ml_id, ia_id, "es_tipo_de")
    save_hierarchy(user.id, dl_id, ml_id, "es_tipo_de")

    tree = get_concept_tree(user.id)

    assert isinstance(tree, dict), "get_concept_tree debe retornar un dict."
    assert "Inteligencia Artificial" in tree, "La raíz debe estar en el árbol."

    ia_node = tree["Inteligencia Artificial"]
    assert "children" in ia_node
    assert "Machine Learning" in ia_node["children"]

    ml_node = ia_node["children"]["Machine Learning"]
    assert "Deep Learning" in ml_node["children"]


# ── 4. hierarchy_agent retorna lista (mock Gemini) ────────────────────────────

def test_hierarchy_agent_returns_list():
    """detect_hierarchy con Gemini mockeado retorna una lista de dicts."""
    from agents.hierarchy_agent import detect_hierarchy

    new_concept = {"id": 2, "term": "Machine Learning", "category": "IA"}
    existing    = [{"id": 1, "term": "Inteligencia Artificial", "category": "IA"}]

    gemini_response = '[{"child_id": 2, "parent_id": 1, "relation_type": "es_tipo_de"}]'

    mock_msg = MagicMock()
    mock_msg.content = gemini_response

    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as MockLLM:
        MockLLM.return_value.invoke.return_value = mock_msg
        result = detect_hierarchy(new_concept, existing, {"learning_area": "IA"})

    assert isinstance(result, list), "detect_hierarchy debe retornar una lista."
    assert len(result) == 1
    assert result[0]["child_id"]      == 2
    assert result[0]["parent_id"]     == 1
    assert result[0]["relation_type"] == "es_tipo_de"


# ── 5. hierarchy_agent → lista vacía si Gemini falla ─────────────────────────

def test_hierarchy_agent_empty_on_failure():
    """Si Gemini lanza excepción, detect_hierarchy retorna lista vacía."""
    from agents.hierarchy_agent import detect_hierarchy

    new_concept = {"id": 2, "term": "Machine Learning", "category": "IA"}
    existing    = [{"id": 1, "term": "Inteligencia Artificial", "category": "IA"}]

    with patch("langchain_google_genai.ChatGoogleGenerativeAI") as MockLLM:
        MockLLM.return_value.invoke.side_effect = RuntimeError("API down")
        result = detect_hierarchy(new_concept, existing, {})

    assert result == [], "Si Gemini falla, detect_hierarchy debe retornar []."


# ── 6. /arbol retorna texto no vacío ─────────────────────────────────────────

def test_arbol_command_returns_text(tmp_db):
    """handle_arbol con árbol vacío retorna string informativo no vacío."""
    from bot.handlers import handle_arbol

    user = create_user("carlos28", "pass123")
    result = handle_arbol(99, user.id, category=None)

    assert isinstance(result, str), "handle_arbol debe retornar un string."
    assert len(result.strip()) > 0, "handle_arbol no debe retornar cadena vacía."


# ── 7. /arbol [categoría] filtra correctamente ───────────────────────────────

def test_arbol_with_category_filters(tmp_db):
    """handle_arbol con categoría solo muestra conceptos de esa categoría."""
    from bot.handlers import handle_arbol

    user      = create_user("diana28", "pass123")
    ml_id     = _make_concept(tmp_db, user.id, "Machine Learning", "IA")
    ia_id     = _make_concept(tmp_db, user.id, "Inteligencia Artificial", "IA")
    fin_id    = _make_concept(tmp_db, user.id, "Amortización", "Finanzas")

    save_hierarchy(user.id, ml_id, ia_id, "es_tipo_de")

    result_ia  = handle_arbol(99, user.id, category="IA")
    result_fin = handle_arbol(99, user.id, category="Finanzas")

    assert "Machine Learning" in result_ia or "Inteligencia" in result_ia, (
        "El árbol filtrado por IA debe contener conceptos de IA."
    )
    assert "Amortización" not in result_ia, (
        "El árbol filtrado por IA no debe contener conceptos de Finanzas."
    )
