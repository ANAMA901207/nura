"""
tests/test_sprint14.py
======================
Harness de verificación para el Sprint 14 de Nura — UX e Interacción.

Pruebas
-------
1. test_ambiguous_term_activates_clarify     — término ambiguo → mode='clarify'
2. test_delete_concept_removes_concept       — delete_concept borra concepto y conexiones
3. test_update_concept_fields_persists       — update_concept_fields persiste cambios (incluyendo term)
4. test_map_filter_logic                     — filtro de mapa devuelve solo nodo y conexiones directas
5. test_spelling_check_activates_spelling    — posible typo → mode='spelling'
"""

from __future__ import annotations

import tempfile
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Fixture de BD aislada ─────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """
    Proporciona una BD temporal aislada para cada test.

    Parchea DB_PATH en db.schema para que init_db() y todas las operaciones
    usen el archivo temporal en lugar de db/nura.db.
    """
    db_file = tmp_path / "test_sprint14.db"
    with patch("db.schema.DB_PATH", str(db_file)):
        from db.schema import init_db
        init_db()
        yield db_file


# ── Test 1: término ambiguo activa mode='clarify' ─────────────────────────────

def test_ambiguous_term_activates_clarify(tmp_db):
    """
    Cuando _is_ambiguous devuelve ambiguous=True, capture_agent debe establecer
    mode='clarify' y almacenar las opciones en clarification_options.
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from agents.capture_agent import capture_agent

        # Simular que Gemini detecta el término como ambiguo
        mock_ambig = {"ambiguous": True, "meanings": ["cursor de base de datos", "Cursor IDE"]}
        with patch("agents.capture_agent._is_ambiguous", return_value=mock_ambig):
            with patch("agents.capture_agent._check_spelling",
                       return_value={"has_typo": False, "suggested": None}):
                state = {
                    "user_input": "cursor",
                    "user_context": "",
                    "user_id": 1,
                    "mode": "",
                    "current_concept": None,
                    "all_concepts": [],
                    "new_connections": [],
                    "response": "",
                    "quiz_questions": [],
                    "sources": [],
                    "insight_message": "",
                    "clarification_options": [],
                    "spelling_suggestion": "",
                }
                result = capture_agent(state)

    assert result["mode"] == "clarify", (
        f"Esperado mode='clarify', obtenido '{result['mode']}'"
    )
    assert len(result.get("clarification_options", [])) >= 2, (
        "clarification_options debe contener al menos 2 significados"
    )


# ── Test 2: delete_concept elimina concepto y conexiones ─────────────────────

def test_delete_concept_removes_concept_and_connections(tmp_db):
    """
    delete_concept(concept_id, user_id) debe eliminar el concepto de la tabla
    concepts y todas sus conexiones asociadas de la tabla connections.
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from db.operations import (
            save_concept, save_connection, get_concept_by_id,
            get_connections_for_concept, delete_concept,
        )

        # Crear dos conceptos y una conexión entre ellos
        c1 = save_concept("interes_compuesto", "test", user_id=1)
        c2 = save_concept("valor_presente", "test", user_id=1)
        save_connection(c1.id, c2.id, "relacionado con", user_id=1)

        # Verificar que la conexión existe
        conns_before = get_connections_for_concept(c1.id, user_id=1)
        assert len(conns_before) == 1, "Debe haber 1 conexión antes de eliminar"

        # Eliminar c1
        deleted = delete_concept(c1.id, user_id=1)
        assert deleted is True, "delete_concept debe retornar True"

        # El concepto ya no debe existir — get_concept_by_id lanza ValueError si no lo encuentra
        with pytest.raises(ValueError):
            get_concept_by_id(c1.id, user_id=1)

        # Las conexiones también deben haberse eliminado
        conns_after = get_connections_for_concept(c2.id, user_id=1)
        assert len(conns_after) == 0, (
            "Las conexiones del concepto eliminado deben borrarse en cascada"
        )


# ── Test 3: update_concept_fields persiste cambios (incluyendo term) ──────────

def test_update_concept_fields_persists(tmp_db):
    """
    update_concept_fields debe persistir correctamente cambios en term, category
    y explanation, y devolver el concepto actualizado.
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from db.operations import save_concept, update_concept_fields, get_concept_by_id

        c = save_concept("EBITAD", "test", user_id=1)   # typo intencional

        updated = update_concept_fields(
            c.id,
            user_id=1,
            term="EBITDA",
            category="Finanzas",
            explanation="Ganancias antes de intereses, impuestos, depreciación y amortización.",
        )

        assert updated.term == "EBITDA", "El term debe haberse actualizado"
        assert updated.category == "Finanzas", "La categoría debe haberse actualizado"
        assert "Ganancias" in updated.explanation, "La explicación debe haberse actualizado"

        # Verificar persistencia en BD
        persisted = get_concept_by_id(c.id, user_id=1)
        assert persisted.term == "EBITDA"
        assert persisted.category == "Finanzas"


# ── Test 4: filtro de mapa retorna solo nodo y conexiones directas ────────────

def test_map_filter_logic(tmp_db):
    """
    Dado un concepto focal, el filtro de mapa debe devolver solo ese nodo y sus
    vecinos directos, excluyendo el resto del grafo.

    Este test verifica la lógica de filtrado directamente (sin UI).
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from db.operations import save_concept, save_connection, get_all_concepts
        from db.schema import get_connection as get_db_conn

        # Crear 4 conceptos con conexiones: A-B, A-C, D-E (D desconectado de A)
        a = save_concept("A_concepto", "test", user_id=1)
        b = save_concept("B_concepto", "test", user_id=1)
        c = save_concept("C_concepto", "test", user_id=1)
        d = save_concept("D_concepto", "test", user_id=1)
        e = save_concept("E_concepto", "test", user_id=1)

        save_connection(a.id, b.id, "relacionado", user_id=1)
        save_connection(a.id, c.id, "relacionado", user_id=1)
        save_connection(d.id, e.id, "relacionado", user_id=1)

        # Obtener todas las conexiones
        with get_db_conn() as conn_db:
            rows = conn_db.execute(
                "SELECT concept_id_a, concept_id_b FROM connections"
            ).fetchall()

        all_conns_raw = [{"concept_id_a": r[0], "concept_id_b": r[1]} for r in rows]

        # Simular la lógica de filtrado del mapa para el nodo focal = A
        focal_id = a.id
        direct_conns = [
            cn for cn in all_conns_raw
            if cn["concept_id_a"] == focal_id or cn["concept_id_b"] == focal_id
        ]
        neighbor_ids = {focal_id}
        for cn in direct_conns:
            neighbor_ids.add(cn["concept_id_a"])
            neighbor_ids.add(cn["concept_id_b"])

        all_concepts = get_all_concepts(user_id=1)
        focal_subset = [c for c in all_concepts if c.id in neighbor_ids]

        # El subgrafo debe contener A, B, C pero NO D ni E
        focal_subset_ids = {c.id for c in focal_subset}
        assert a.id in focal_subset_ids, "El nodo focal debe estar en el subgrafo"
        assert b.id in focal_subset_ids, "B (vecino de A) debe estar en el subgrafo"
        assert c.id in focal_subset_ids, "C (vecino de A) debe estar en el subgrafo"
        assert d.id not in focal_subset_ids, "D (desconectado) NO debe estar en el subgrafo"
        assert e.id not in focal_subset_ids, "E (desconectado) NO debe estar en el subgrafo"
        assert len(direct_conns) == 2, "El subgrafo debe tener exactamente 2 conexiones directas"


# ── Test 5: término con typo activa mode='spelling' ───────────────────────────

def test_spelling_check_activates_spelling(tmp_db):
    """
    Cuando _check_spelling detecta un posible typo, capture_agent debe
    establecer mode='spelling' y guardar la sugerencia en spelling_suggestion.
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from agents.capture_agent import capture_agent

        mock_spelling = {"has_typo": True, "suggested": "EBITDA"}
        with patch("agents.capture_agent._check_spelling", return_value=mock_spelling):
            with patch("agents.capture_agent._is_ambiguous",
                       return_value={"ambiguous": False, "meanings": []}):
                state = {
                    "user_input": "EBITAD",
                    "user_context": "",
                    "user_id": 1,
                    "mode": "",
                    "current_concept": None,
                    "all_concepts": [],
                    "new_connections": [],
                    "response": "",
                    "quiz_questions": [],
                    "sources": [],
                    "insight_message": "",
                    "clarification_options": [],
                    "spelling_suggestion": "",
                }
                result = capture_agent(state)

    assert result["mode"] == "spelling", (
        f"Esperado mode='spelling', obtenido '{result['mode']}'"
    )
    assert result.get("spelling_suggestion") == "EBITDA", (
        "spelling_suggestion debe contener la corrección sugerida"
    )
