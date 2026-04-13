"""
tests/test_sprint15.py
======================
Harness de verificación para el Sprint 15 de Nura — Onboarding y perfil de usuario.

Pruebas
-------
1. test_update_user_profile_persists         — update_user_profile persiste los tres campos
2. test_needs_onboarding_with_empty_fields   — needs_onboarding → True con campos vacíos
3. test_needs_onboarding_with_full_profile   — needs_onboarding → False con perfil completo
4. test_classifier_receives_user_profile     — classifier incluye user_profile del state
5. test_tutor_receives_user_profile          — tutor usa user_profile del state en su prompt
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


# ── Fixture de BD aislada ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """
    Proporciona una BD temporal aislada para cada test.

    Parchea DB_PATH en db.schema para que init_db() y todas las operaciones
    usen el archivo temporal en lugar de db/nura.db.
    """
    db_file = tmp_path / "test_sprint15.db"
    with patch("db.schema.DB_PATH", str(db_file)):
        from db.schema import init_db
        init_db()
        yield db_file


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_user(
    *,
    profession: str = "",
    learning_area: str = "",
    tech_level: str = "",
) -> "User":
    """Crea un objeto User en memoria para tests que no requieren BD."""
    from db.models import User
    return User(
        id=1,
        username="tester",
        password_hash="$2b$12$fakehash",
        created_at=datetime(2026, 1, 1),
        profession=profession,
        learning_area=learning_area,
        tech_level=tech_level,
    )


# ── Test 1: update_user_profile persiste los tres campos ──────────────────────

def test_update_user_profile_persists(tmp_db):
    """
    update_user_profile(user_id, profession, learning_area, tech_level) debe
    escribir los tres valores en la BD y devolver el User actualizado.
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from db.operations import create_user, update_user_profile

        user = create_user("testuser_15", "password123")
        updated = update_user_profile(
            user.id,
            profession="Desarrollador/ingeniero",
            learning_area="IA y tecnología",
            tech_level="Intermedio",
        )

    assert updated.profession    == "Desarrollador/ingeniero", (
        "profession no se persistió correctamente"
    )
    assert updated.learning_area == "IA y tecnología", (
        "learning_area no se persistió correctamente"
    )
    assert updated.tech_level    == "Intermedio", (
        "tech_level no se persistió correctamente"
    )


# ── Test 2: needs_onboarding devuelve True con campos vacíos ──────────────────

def test_needs_onboarding_with_empty_fields():
    """
    needs_onboarding debe devolver True cuando al menos uno de los tres campos
    del perfil está vacío (caso típico de usuario recién registrado).
    """
    from db.operations import needs_onboarding

    # Ningún campo rellenado
    assert needs_onboarding(_make_user()) is True, (
        "Con todos los campos vacíos, needs_onboarding debe ser True"
    )
    # Solo profession rellenado
    assert needs_onboarding(_make_user(profession="Estudiante")) is True, (
        "Con learning_area y tech_level vacíos, needs_onboarding debe ser True"
    )
    # Dos campos rellenados, falta tech_level
    assert needs_onboarding(
        _make_user(profession="Estudiante", learning_area="Ambas")
    ) is True, "Con tech_level vacío, needs_onboarding debe ser True"


# ── Test 3: needs_onboarding devuelve False con perfil completo ───────────────

def test_needs_onboarding_with_full_profile():
    """
    needs_onboarding debe devolver False cuando los tres campos del perfil
    están rellenos (onboarding completado).
    """
    from db.operations import needs_onboarding

    full_user = _make_user(
        profession="Emprendedor/negocios",
        learning_area="Finanzas y negocios",
        tech_level="Avanzado",
    )
    assert needs_onboarding(full_user) is False, (
        "Con los tres campos rellenos, needs_onboarding debe ser False"
    )


# ── Test 4: classifier recibe user_profile del state ─────────────────────────

def test_classifier_receives_user_profile(tmp_db):
    """
    classifier_agent debe extraer user_profile del state y pasarlo como
    user_context al llamar a classify_concept, incluyendo la profesión y
    el área del usuario para personalizar los ejemplos.
    """
    with patch("db.schema.DB_PATH", str(tmp_db)):
        from db.operations import save_concept
        from agents.classifier_agent import classifier_agent

        concept = save_concept("spread_crediticio", "test", user_id=1)

        # Capturamos el user_context que llega a classify_concept
        captured_context: dict = {}

        def _mock_classify(term, context="", user_context=""):
            captured_context["user_context"] = user_context
            return {
                "category": "Finanzas", "subcategory": "Crédito",
                "explanation": "Diferencial de rendimiento",
                "how_it_works": "", "schema": "", "analogy": "",
                "example": "", "flashcard_front": "¿Qué es?",
                "flashcard_back": "Diferencial",
            }

        profile = {
            "profession":    "Analista de crédito/banca",
            "learning_area": "Finanzas y negocios",
            "tech_level":    "Intermedio",
        }

        state = {
            "user_input": "spread_crediticio",
            "user_context": "",
            "current_concept": concept,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "capture",
            "user_id": 1,
            "quiz_questions": [],
            "sources": [],
            "insight_message": "",
            "clarification_options": [],
            "spelling_suggestion": "",
            "user_profile": profile,
        }

        with patch("agents.classifier_agent.classify_concept", side_effect=_mock_classify):
            classifier_agent(state)

    ctx = captured_context.get("user_context", "")
    assert "Analista de crédito/banca" in ctx or "banca" in ctx.lower(), (
        "El user_context debe incluir información del perfil del usuario"
    )


# ── Test 5: tutor recibe user_profile del state ───────────────────────────────

def test_tutor_receives_user_profile():
    """
    _build_tutor_system_prompt debe devolver un prompt que incluya información
    del perfil del usuario cuando los campos están rellenos.
    """
    from agents.tutor_agent import _build_tutor_system_prompt

    # Perfil vacío — debe devolver el prompt base sin modificar
    base_prompt = _build_tutor_system_prompt({})
    assert "Nura" in base_prompt, "El prompt base debe mencionar Nura"

    # Perfil de analista bancario
    banking_prompt = _build_tutor_system_prompt({
        "profession":    "Analista de crédito/banca",
        "learning_area": "Finanzas y negocios",
        "tech_level":    "Intermedio",
    })
    assert len(banking_prompt) > len(base_prompt), (
        "El prompt con perfil debe ser más largo que el base"
    )
    assert "crédito" in banking_prompt.lower() or "banca" in banking_prompt.lower(), (
        "El prompt para analista bancario debe mencionar crédito o banca"
    )

    # Perfil de desarrollador
    dev_prompt = _build_tutor_system_prompt({
        "profession":    "Desarrollador/ingeniero",
        "learning_area": "IA y tecnología",
        "tech_level":    "Avanzado",
    })
    assert "código" in dev_prompt.lower() or "arquitectura" in dev_prompt.lower(), (
        "El prompt para desarrollador debe mencionar código o arquitectura"
    )
