"""
tests/test_sprint8.py
=====================
Harness de verificación para el Sprint 8 de Nura — algoritmo SM-2.

Verificaciones obligatorias (5/5):
    1. Acierto actualiza sm2_ef correctamente (permanece >= 1.3, no sube con q=4).
    2. Error baja sm2_ef 0.2 y resetea sm2_interval a 1.
    3. sm2_ef nunca baja de 1.3 sin importar cuántos errores consecutivos.
    4. Concepto con next_review = hoy aparece en get_concepts_due_today().
    5. Concepto con next_review = mañana NO aparece en get_concepts_due_today().

Cada test trabaja con una BD SQLite temporal aislada para no contaminar
la BD de producción.  El setup inyecta directamente valores SM-2 en la BD
para reproducir escenarios deterministas sin depender de la API de Gemini.
"""

from __future__ import annotations

import sys
import os
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, date

# Permite importar desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

import db.schema as schema_module
from db.schema import init_db
from db.operations import (
    record_flashcard_result,
    get_concepts_due_today,
    save_concept,
    update_concept_fields,
)


# ── helpers de setup ──────────────────────────────────────────────────────────

def _make_temp_db() -> tempfile.NamedTemporaryFile:
    """
    Crea un archivo temporal que se usa como BD SQLite aislada para el test.

    Devuelve el objeto NamedTemporaryFile; el llamador es responsable de
    restaurar schema_module.DB_PATH a su valor original después de usarlo.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp


def _setup_db(tmp_path: str) -> None:
    """
    Apunta schema_module a la BD temporal y la inicializa con las migraciones.

    Parámetros
    ----------
    tmp_path : Ruta absoluta al archivo .db temporal.
    """
    schema_module.DB_PATH = Path(tmp_path)
    init_db()


def _teardown_db(tmp_path: str, original_path: Path) -> None:
    """
    Restaura la ruta original de la BD y borra el archivo temporal.

    Parámetros
    ----------
    tmp_path     : Ruta al archivo temporal a eliminar.
    original_path: Valor original de schema_module.DB_PATH.
    """
    schema_module.DB_PATH = original_path
    try:
        os.unlink(tmp_path)
    except OSError:
        pass  # En Windows puede fallar si la conexión no se cerró del todo


def _set_sm2_fields(tmp_path: str, concept_id: int, **kwargs) -> None:
    """
    Actualiza directamente columnas SM-2 en la BD para configurar escenarios de test.

    Recibe kwargs con cualquier combinación de: sm2_ef, sm2_interval,
    consecutive_correct, consecutive_incorrect, next_review (str ISO).

    Parámetros
    ----------
    tmp_path   : Ruta al archivo .db a modificar.
    concept_id : ID del concepto a actualizar.
    **kwargs   : Campos y valores a establecer.
    """
    allowed = {"sm2_ef", "sm2_interval", "consecutive_correct",
               "consecutive_incorrect", "next_review", "mastery_level",
               "is_classified"}
    sets = ", ".join(f"{k} = ?" for k in kwargs if k in allowed)
    vals = [v for k, v in kwargs.items() if k in allowed]
    vals.append(concept_id)
    conn = sqlite3.connect(tmp_path)
    conn.execute(f"UPDATE concepts SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()


# ── tests ────────────────────────────────────────────────────────────────────

def test_correct_updates_ef() -> tuple[bool, str]:
    """
    Verificación 1: un acierto aplica la fórmula SM-2 EF sin bajar de 1.3.

    Con q=4 la fórmula produce new_ef = ef + 0.0, es decir, el EF no cambia
    en el primer acierto (comportamiento correcto de SM-2 con q=4).
    Verificamos que sm2_ef >= 1.3 y que sm2_interval se actualiza correctamente
    (primer acierto → intervalo 1).
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)
        concept = save_concept("TestEF", "test")
        # Asegura is_classified=True y ef inicial conocido
        _set_sm2_fields(tmp.name, concept.id, sm2_ef=2.5, sm2_interval=1.0,
                        consecutive_correct=0, is_classified=1)

        updated = record_flashcard_result(concept.id, correct=True)

        # Con q=4: new_ef = 2.5 + (0.1 - 1*(0.08+1*0.02)) = 2.5 + 0.0 = 2.5
        ef_ok = abs(updated.sm2_ef - 2.5) < 1e-9
        ef_floor_ok = updated.sm2_ef >= 1.3
        interval_ok = updated.sm2_interval == 1.0  # primer acierto → 1 día

        if ef_ok and ef_floor_ok and interval_ok:
            return True, f"sm2_ef={updated.sm2_ef:.4f}, sm2_interval={updated.sm2_interval}"
        return False, (
            f"sm2_ef={updated.sm2_ef} (esperado 2.5), "
            f"sm2_interval={updated.sm2_interval} (esperado 1.0)"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_incorrect_lowers_ef_and_resets_interval() -> tuple[bool, str]:
    """
    Verificación 2: un error baja sm2_ef en 0.2 y resetea sm2_interval a 1.

    Partimos de ef=2.5, interval=10.  Después del error esperamos
    ef=2.3 e interval=1.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)
        concept = save_concept("TestError", "test")
        _set_sm2_fields(tmp.name, concept.id, sm2_ef=2.5, sm2_interval=10.0,
                        consecutive_correct=3)

        updated = record_flashcard_result(concept.id, correct=False)

        ef_ok = abs(updated.sm2_ef - 2.3) < 1e-9
        interval_ok = updated.sm2_interval == 1.0

        if ef_ok and interval_ok:
            return True, f"sm2_ef={updated.sm2_ef:.4f}, sm2_interval={updated.sm2_interval}"
        return False, (
            f"sm2_ef={updated.sm2_ef:.4f} (esperado 2.3), "
            f"sm2_interval={updated.sm2_interval} (esperado 1.0)"
        )
    except Exception as exc:
        return False, str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_ef_never_below_floor() -> tuple[bool, str]:
    """
    Verificación 3: sm2_ef nunca baja de 1.3 sin importar cuántos errores.

    Partimos de ef=1.3 (el mínimo) y registramos un error.  El resultado
    debe seguir siendo exactamente 1.3.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)
        concept = save_concept("TestFloor", "test")
        _set_sm2_fields(tmp.name, concept.id, sm2_ef=1.3, sm2_interval=1.0)

        updated = record_flashcard_result(concept.id, correct=False)

        floor_ok = abs(updated.sm2_ef - 1.3) < 1e-9 and updated.sm2_ef >= 1.3
        if floor_ok:
            return True, f"sm2_ef={updated.sm2_ef:.4f} (>= 1.3 correcto)"
        return False, f"sm2_ef={updated.sm2_ef:.4f} (bajó de 1.3, no debería)"
    except Exception as exc:
        return False, str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_concept_due_today_appears() -> tuple[bool, str]:
    """
    Verificación 4: concepto con next_review=hoy aparece en get_concepts_due_today().

    El concepto debe tener is_classified=True y next_review = hoy (a medianoche).
    La función debe devolverlo en la lista.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)
        concept = save_concept("DueToday", "test")
        today_str = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        _set_sm2_fields(tmp.name, concept.id, next_review=today_str, is_classified=1)

        due = get_concepts_due_today()
        ids = [c.id for c in due]

        if concept.id in ids:
            return True, f"Concepto {concept.id} presente en due_today ({len(due)} total)"
        return False, f"Concepto {concept.id} NO encontrado; due_today ids={ids}"
    except Exception as exc:
        return False, str(exc)
    finally:
        _teardown_db(tmp.name, original)


def test_concept_due_tomorrow_not_appears() -> tuple[bool, str]:
    """
    Verificación 5: concepto con next_review=mañana NO aparece en get_concepts_due_today().

    Solo deben aparecer los conceptos con next_review <= hoy.  Mañana queda
    fuera del filtro.
    """
    original = schema_module.DB_PATH
    tmp = _make_temp_db()
    try:
        _setup_db(tmp.name)
        concept = save_concept("DueTomorrow", "test")
        tomorrow_str = (datetime.now() + timedelta(days=1)).isoformat()
        _set_sm2_fields(tmp.name, concept.id, next_review=tomorrow_str, is_classified=1)

        due = get_concepts_due_today()
        ids = [c.id for c in due]

        if concept.id not in ids:
            return True, f"Concepto {concept.id} correctamente ausente; due_today ids={ids}"
        return False, f"Concepto {concept.id} aparece aunque su next_review es mañana"
    except Exception as exc:
        return False, str(exc)
    finally:
        _teardown_db(tmp.name, original)


# ── runner ────────────────────────────────────────────────────────────────────

def _run_all() -> None:
    """
    Ejecuta todos los tests del Sprint 8 y reporta el resultado por consola.

    Formato de salida:
        [PASS] Descripcion breve - detalle
        [FAIL] Descripcion breve - mensaje de error
    Al final imprime el marcador X/5 passed.
    """
    tests = [
        ("Acierto actualiza EF correctamente (q=4, EF estable)", test_correct_updates_ef),
        ("Error baja EF 0.2 y resetea intervalo a 1",            test_incorrect_lowers_ef_and_resets_interval),
        ("EF nunca baja de 1.3 (floor garantizado)",             test_ef_never_below_floor),
        ("Concepto con next_review=hoy aparece en due_today",    test_concept_due_today_appears),
        ("Concepto con next_review=manana NO aparece",           test_concept_due_tomorrow_not_appears),
    ]

    passed = 0
    print("\n=== Sprint 8 - SM-2 Spaced Repetition ===\n")
    for name, fn in tests:
        try:
            ok, detail = fn()
        except Exception as exc:
            ok, detail = False, f"Excepcion no capturada: {exc}"

        status = "PASS" if ok else "FAIL"
        safe_detail = detail.encode("ascii", "replace").decode("ascii")
        print(f"  [{status}] {name}")
        print(f"         {safe_detail}")
        if ok:
            passed += 1

    total = len(tests)
    print(f"\n  {passed}/{total} passed\n")


if __name__ == "__main__":
    _run_all()
