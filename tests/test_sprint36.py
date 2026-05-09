"""
tests/test_sprint36.py
======================
Sprint 36 — Mapa jerárquico visual (SVG + mini en cards).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("DATABASE_URL", "")

import db.schema as _schema
from db.schema import init_db
from db.operations import create_user, get_concept_tree, save_hierarchy


@pytest.fixture()
def tmp_db(tmp_path):
    db_file = tmp_path / "test_s36.db"
    original = _schema.DB_PATH
    original_url = os.environ.get("DATABASE_URL", "")
    _schema.DB_PATH = db_file
    os.environ["DATABASE_URL"] = ""
    init_db()
    yield db_file
    _schema.DB_PATH = original
    os.environ["DATABASE_URL"] = original_url if original_url else ""


def _make_concept(db_path: Path, user_id: int, term: str, category: str = "IA") -> int:
    from datetime import datetime

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
        row = conn.execute(
            "SELECT id FROM concepts WHERE term=? AND user_id=?",
            (term, user_id),
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


def test_render_hierarchy_svg_returns_string():
    from ui.components import render_hierarchy_svg

    out = render_hierarchy_svg({})
    assert isinstance(out, str)
    assert out.strip().startswith("<svg")


def test_hierarchy_svg_empty_tree():
    from ui.components import render_hierarchy_svg

    svg = render_hierarchy_svg({})
    assert "Sin jerarquía registrada" in svg


def test_hierarchy_svg_has_root_node(tmp_db):
    user = create_user("s36root", "pass123")
    ia = _make_concept(tmp_db, user.id, "Inteligencia Artificial", "IA")
    ml = _make_concept(tmp_db, user.id, "Machine Learning", "IA")
    save_hierarchy(user.id, ml, ia, "es_tipo_de")

    from ui.components import render_hierarchy_svg

    tree = get_concept_tree(user.id)
    svg = render_hierarchy_svg(tree)
    assert "Inteligencia Artificial" in svg


def test_hierarchy_svg_contains_highlighted_node(tmp_db):
    user = create_user("s36hi", "pass123")
    ia = _make_concept(tmp_db, user.id, "Inteligencia Artificial", "IA")
    ml = _make_concept(tmp_db, user.id, "Machine Learning", "IA")
    save_hierarchy(user.id, ml, ia, "es_tipo_de")

    from ui.components import render_hierarchy_svg

    tree = get_concept_tree(user.id)
    svg = render_hierarchy_svg(tree, highlighted_id=ml, user_id=user.id)
    assert "#534AB7" in svg or svg.lower().count("534ab7") >= 1
    assert "estás aquí" in svg or "est&#225;s aqu&#237;" in svg


def test_render_concept_hierarchy_mini_no_hierarchy(tmp_db):
    user = create_user("s36mini", "pass123")
    cid = _make_concept(tmp_db, user.id, "Solo Concepto", "Finanzas")

    from ui.components import render_concept_hierarchy_mini

    with (
        patch("streamlit.caption") as mock_cap,
        patch("streamlit.components.v1.html") as mock_html,
    ):
        render_concept_hierarchy_mini(user.id, cid)

    mock_cap.assert_called_once()
    _arg0 = mock_cap.call_args[0][0]
    assert "Categoría" in _arg0 or "Categor" in _arg0
    mock_html.assert_not_called()
