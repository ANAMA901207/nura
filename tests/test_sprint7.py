"""
tests/test_sprint7.py
=====================
Harness de verificación — Sprint 7: Flashcards inteligentes con dominio real.

Todos los tests son deterministas (sin llamadas a la API de Gemini).

Ejecutar con:
    python tests/test_sprint7.py
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
    update_concept_fields,
    record_flashcard_result,
    get_concept_by_id,
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


def _make_concept(term: str, mastery: int = 0) -> object:
    """Crea un concepto de prueba con mastery inicial dado."""
    c = save_concept(term=term, context="test")
    if mastery > 0:
        from db.operations import update_mastery_level
        c = update_mastery_level(c.id, mastery)
    return c


# ── tests ─────────────────────────────────────────────────────────────────────

def test_first_correct_raises_mastery_to_2() -> None:
    """
    (1) Un acierto sube mastery de 0 a 2 (o a max(actual, 2)).

    Verifica que tras el primer acierto (consecutive_correct == 1):
    - mastery_level == 2
    - consecutive_correct == 1
    - consecutive_incorrect == 0
    - total_reviews == 1
    - next_review no es None
    """
    _reset_db()
    concept = _make_concept("tasa_interes", mastery=0)
    assert concept.mastery_level == 0

    updated = record_flashcard_result(concept.id, correct=True)

    assert updated.mastery_level == 2, (
        f"Primer acierto debe llevar mastery a 2, se obtuvo {updated.mastery_level}"
    )
    assert updated.consecutive_correct == 1
    assert updated.consecutive_incorrect == 0
    assert updated.total_reviews == 1
    assert updated.next_review is not None, "next_review debe programarse tras el acierto"

    print("  [1] Primer acierto sube mastery de 0 a 2: OK")


def test_three_consecutive_correct_raises_mastery_to_3() -> None:
    """
    (2) 3 aciertos consecutivos suben mastery a 3.

    Llama a record_flashcard_result(True) tres veces seguidas y verifica
    que mastery_level llega a 3 y consecutive_correct == 3.
    """
    _reset_db()
    concept = _make_concept("amortizacion", mastery=0)

    c = record_flashcard_result(concept.id, correct=True)  # consec=1, mastery=2
    c = record_flashcard_result(concept.id, correct=True)  # consec=2, mastery=2
    c = record_flashcard_result(concept.id, correct=True)  # consec=3, mastery=3

    assert c.mastery_level == 3, (
        f"3 aciertos consecutivos deben llevar mastery a 3, se obtuvo {c.mastery_level}"
    )
    assert c.consecutive_correct == 3
    assert c.total_reviews == 3

    print("  [2] 3 aciertos consecutivos suben mastery a 3: OK")


def test_three_consecutive_incorrect_lowers_mastery() -> None:
    """
    (3) 3 errores consecutivos bajan mastery en 1.

    Parte de mastery=3, aplica 3 errores seguidos y verifica que mastery
    baja a 2.  También verifica que consecutive_incorrect se incrementa
    y consecutive_correct se resetea.
    """
    _reset_db()
    concept = _make_concept("provision", mastery=3)
    assert concept.mastery_level == 3

    c = record_flashcard_result(concept.id, correct=False)  # consec_err=1, mastery=3
    assert c.mastery_level == 3, "1 error no debe bajar el nivel"

    c = record_flashcard_result(concept.id, correct=False)  # consec_err=2, mastery=3
    assert c.mastery_level == 3, "2 errores consecutivos no deben bajar el nivel"

    c = record_flashcard_result(concept.id, correct=False)  # consec_err=3, mastery→2
    assert c.mastery_level == 2, (
        f"3 errores consecutivos deben bajar mastery en 1 (de 3 a 2), "
        f"se obtuvo {c.mastery_level}"
    )
    assert c.consecutive_incorrect == 3
    assert c.consecutive_correct == 0
    assert c.total_reviews == 3

    print("  [3] 3 errores consecutivos bajan mastery en 1: OK")


def test_error_after_correct_resets_consecutive_correct() -> None:
    """
    (4) Un error después de aciertos resetea consecutive_correct a 0.

    Acumula 2 aciertos consecutivos (consecutive_correct=2), luego un error.
    Verifica que consecutive_correct vuelve a 0 y consecutive_incorrect pasa a 1.
    """
    _reset_db()
    concept = _make_concept("cartera_vencida", mastery=0)

    c = record_flashcard_result(concept.id, correct=True)   # consec_c=1
    c = record_flashcard_result(concept.id, correct=True)   # consec_c=2
    assert c.consecutive_correct == 2, "Deben acumularse 2 aciertos consecutivos"

    c = record_flashcard_result(concept.id, correct=False)  # resetea consec_c
    assert c.consecutive_correct == 0, (
        "Un error debe resetear consecutive_correct a 0"
    )
    assert c.consecutive_incorrect == 1, (
        "El primer error debe establecer consecutive_incorrect en 1"
    )
    assert c.total_reviews == 3

    print("  [4] Error resetea consecutive_correct a 0: OK")


def test_session_counts_correct_and_incorrect() -> None:
    """
    (5) El resumen de sesión cuenta correctamente aciertos y errores.

    Simula una sesión de 3 tarjetas: aplica múltiples llamadas a
    record_flashcard_result y verifica los contadores acumulados.
    Comprueba también que conceptos con más aciertos suben más de nivel.
    """
    _reset_db()
    c1 = _make_concept("langgraph", mastery=0)
    c2 = _make_concept("openrouter", mastery=0)
    c3 = _make_concept("embedding", mastery=2)

    # c1: 1 acierto → mastery 2
    r1 = record_flashcard_result(c1.id, correct=True)
    assert r1.mastery_level == 2
    assert r1.total_reviews == 1

    # c2: 1 error, luego 1 acierto → mastery llega a 2
    record_flashcard_result(c2.id, correct=False)
    r2 = record_flashcard_result(c2.id, correct=True)
    assert r2.consecutive_correct == 1
    assert r2.total_reviews == 2

    # c3: 3 aciertos seguidos desde mastery=2 → mastery 3
    record_flashcard_result(c3.id, correct=True)
    record_flashcard_result(c3.id, correct=True)
    r3 = record_flashcard_result(c3.id, correct=True)
    assert r3.mastery_level == 3
    assert r3.consecutive_correct == 3
    assert r3.total_reviews == 3

    # Verificar conteos en BD
    final_c1 = get_concept_by_id(c1.id)
    final_c2 = get_concept_by_id(c2.id)
    final_c3 = get_concept_by_id(c3.id)

    assert final_c1.total_reviews == 1, f"c1: 1 revision, se obtuvo {final_c1.total_reviews}"
    assert final_c2.total_reviews == 2, f"c2: 2 revisiones, se obtuvo {final_c2.total_reviews}"
    assert final_c3.total_reviews == 3, f"c3: 3 revisiones, se obtuvo {final_c3.total_reviews}"

    # Verificar que los niveles subieron respecto a sus valores iniciales
    assert final_c1.mastery_level > 0, "c1 debe haber subido de nivel"
    assert final_c3.mastery_level > 2, "c3 debe haber superado mastery=2"

    print("  [5] Conteos de sesion correctos y niveles actualizados: OK")


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """Ejecuta todos los tests y reporta el resultado final."""
    tests = [
        test_first_correct_raises_mastery_to_2,
        test_three_consecutive_correct_raises_mastery_to_3,
        test_three_consecutive_incorrect_lowers_mastery,
        test_error_after_correct_resets_consecutive_correct,
        test_session_counts_correct_and_incorrect,
    ]

    passed = 0
    failed = 0

    print("\nSprint 7 - Flashcards inteligentes - Test Harness")
    print("=" * 52)

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
    print("=" * 52)
    print(f"Resultado: {passed}/{total} passed", end="")
    print(f"  ({failed} failed)" if failed else "  OK todos pasaron")
    print("=" * 52)

    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _run_all()
