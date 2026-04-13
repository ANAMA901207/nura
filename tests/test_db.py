"""
Harness de verificación — Sprint 1: capa de base de datos de Nura.

Ejecutar con:
    python -m pytest tests/test_db.py -v
o directamente:
    python tests/test_db.py
"""

from __future__ import annotations

import sys
import os
import tempfile
from datetime import date
from pathlib import Path

# Permite importar desde la raíz del proyecto sin instalar el paquete
sys.path.insert(0, str(Path(__file__).parent.parent))

# Redirige la BD a un archivo temporal por cada ejecución de tests
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.schema as _schema
_schema.DB_PATH = Path(_tmp_db.name)

from db.schema import init_db
from db.operations import (
    save_concept,
    get_concept_by_id,
    save_connection,
    get_connections_for_concept,
    update_mastery_level,
    update_concept_classification,
    get_or_create_daily_summary,
    update_daily_summary,
)


# ── fixture ───────────────────────────────────────────────────────────────────

def setup() -> None:
    """Inicializa (o reinicializa) la BD de pruebas antes de cada test."""
    import sqlite3
    conn = sqlite3.connect(str(_schema.DB_PATH))
    conn.executescript("""
        DROP TABLE IF EXISTS connections;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS daily_summaries;
    """)
    conn.close()
    init_db()


# ── tests ─────────────────────────────────────────────────────────────────────

def test_save_and_retrieve_concept_by_id() -> None:
    """(1) Guardar un concepto y recuperarlo por ID devuelve el mismo term."""
    setup()
    saved = save_concept("epistemología", "clase de filosofía")
    fetched = get_concept_by_id(saved.id)
    assert fetched.term == "epistemología", (
        f"Expected 'epistemología', got '{fetched.term}'"
    )
    assert fetched.id == saved.id


def test_connect_concepts_and_retrieve_from_both_sides() -> None:
    """(2) Conectar dos conceptos y recuperar la conexión desde ambos IDs."""
    setup()
    a = save_concept("racionalismo", "historia de la filosofía")
    b = save_concept("empirismo", "historia de la filosofía")
    conn = save_connection(a.id, b.id, "corrientes opuestas")

    from_a = get_connections_for_concept(a.id)
    from_b = get_connections_for_concept(b.id)

    assert any(c.id == conn.id for c in from_a), "Conexión no encontrada desde concept_id_a"
    assert any(c.id == conn.id for c in from_b), "Conexión no encontrada desde concept_id_b"


def test_update_mastery_level_persists() -> None:
    """(3) Actualizar mastery_level persiste correctamente."""
    setup()
    concept = save_concept("lógica", "matemáticas")
    assert concept.mastery_level == 0

    updated = update_mastery_level(concept.id, 4)
    assert updated.mastery_level == 4

    fetched = get_concept_by_id(concept.id)
    assert fetched.mastery_level == 4, (
        f"mastery_level en BD es {fetched.mastery_level}, esperado 4"
    )


def test_daily_summary_create_and_update() -> None:
    """(4) DailySummary se crea si no existe y se actualiza si ya existe."""
    setup()
    today = date(2026, 4, 10)

    summary = get_or_create_daily_summary(today)
    assert summary.concepts_captured == 0
    assert summary.new_connections == 0

    updated = update_daily_summary(today, concepts_captured=3, new_connections=1)
    assert updated.concepts_captured == 3
    assert updated.new_connections == 1

    # Segunda llamada a get_or_create no resetea los valores
    same = get_or_create_daily_summary(today)
    assert same.concepts_captured == 3


def test_duplicate_term_raises_value_error() -> None:
    """(5) Comportamiento correcto ante términos duplicados (Sprint 5+).

    Caso A — is_classified=False (estado por defecto tras captura):
        save_concept() retorna el concepto existente sin lanzar ValueError.
        Esto permite reintentar la clasificación sin crear duplicados.

    Caso B — is_classified=True (concepto ya enriquecido):
        save_concept() lanza ValueError porque el término ya está clasificado
        y no tiene sentido sobrescribirlo silenciosamente.
    """
    from db.operations import update_concept_classification

    setup()

    # ── Caso A: duplicado sin clasificar → retorna el existente ──────────────
    original = save_concept("semiótica", "lingüística")
    # Por defecto is_classified=False; un segundo intento debe retornar el mismo
    returned = save_concept("semiótica", "otro contexto")
    assert returned.id == original.id, (
        "El segundo save_concept debe devolver el concepto existente "
        f"(id={original.id}), no crear uno nuevo (id={returned.id})."
    )
    assert returned.term == "semiótica"

    # ── Caso B: duplicado ya clasificado → ValueError ─────────────────────────
    update_concept_classification(
        original.id,
        {"category": "Humanidades", "subcategory": "Lingüística"},
    )
    try:
        save_concept("semiótica", "tercer intento")
        assert False, "Debía lanzar ValueError por term duplicado ya clasificado"
    except ValueError as exc:
        assert "semiótica" in str(exc).lower() or "already exists" in str(exc).lower()


def test_connection_with_nonexistent_id_raises_value_error() -> None:
    """(6) Conexión con ID inexistente lanza ValueError controlado."""
    setup()
    real = save_concept("ontología", "metafísica")
    fake_id = 99999
    try:
        save_connection(real.id, fake_id, "relación imposible")
        assert False, "Debía lanzar ValueError por ID inexistente"
    except ValueError as exc:
        assert str(fake_id) in str(exc)


# ── runner manual (sin pytest) ────────────────────────────────────────────────

def _run_all() -> None:
    tests = [
        test_save_and_retrieve_concept_by_id,
        test_connect_concepts_and_retrieve_from_both_sides,
        test_update_mastery_level_persists,
        test_daily_summary_create_and_update,
        test_duplicate_term_raises_value_error,
        test_connection_with_nonexistent_id_raises_value_error,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {test.__name__}: {exc}")
            failed += 1

    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Resultado: {passed}/{total} passed", end="")
    if failed:
        print(f"  ({failed} failed)")
    else:
        print("  OK todos pasaron")
    print(f"{'='*50}")

    # Limpieza del archivo temporal
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
