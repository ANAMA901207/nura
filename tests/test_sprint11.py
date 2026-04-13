"""
tests/test_sprint11.py
======================
Harness de verificacion para Sprint 11 — multi-usuario con autenticacion y seguridad.

Tests obligatorios:
  1. create_user hashea password correctamente con bcrypt.
  2. authenticate_user retorna User con credenciales correctas.
  3. authenticate_user retorna None con password incorrecto.
  4. Conceptos de user_id=1 no aparecen en queries de user_id=2.
  5. Input con intento de prompt injection es sanitizado antes de llegar al LLM.

Todos los tests usan una BD temporal aislada que se limpia al finalizar.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Garantiza que el modulo db/ se importa desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))


def _setup_temp_db() -> Path:
    """
    Crea una BD temporal aislada y actualiza DB_PATH en db.schema para que
    todos los modulos usen esa BD durante el test.

    Devuelve
    --------
    Path al archivo temporal de la BD.
    """
    import db.schema as schema
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    schema.DB_PATH = Path(tmp.name)
    from db.schema import init_db
    init_db()
    return Path(tmp.name)


def _cleanup_temp_db(path: Path) -> None:
    """Elimina el archivo de BD temporal."""
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass  # Windows puede bloquear el archivo brevemente; no es critico


class TestCreateUser(unittest.TestCase):
    """Test 1: create_user hashea la contrasena correctamente con bcrypt."""

    def setUp(self):
        self.db_path = _setup_temp_db()

    def tearDown(self):
        _cleanup_temp_db(self.db_path)

    def test_password_is_hashed_with_bcrypt(self):
        """
        Verifica que el hash almacenado sea un hash bcrypt real y que
        no contenga la contrasena en texto plano.
        """
        import bcrypt
        from db.operations import create_user

        user = create_user("alice", "secreto123")

        # El hash debe empezar con $2b$ (indicador bcrypt)
        self.assertTrue(
            user.password_hash.startswith("$2b$"),
            f"Se esperaba hash bcrypt ($2b$...), se obtuvo: {user.password_hash[:20]}"
        )

        # La contrasena en texto plano NO debe estar en el hash
        self.assertNotIn(
            "secreto123",
            user.password_hash,
            "La contrasena en texto plano no debe aparecer en el hash."
        )

        # bcrypt.checkpw debe confirmar que el hash es correcto
        is_valid = bcrypt.checkpw(
            b"secreto123",
            user.password_hash.encode("utf-8"),
        )
        self.assertTrue(is_valid, "bcrypt.checkpw debe confirmar la contrasena original.")

    def test_username_stored_and_id_assigned(self):
        """El usuario devuelto tiene username correcto e id asignado por SQLite."""
        from db.operations import create_user

        user = create_user("bob", "pass456")

        self.assertEqual(user.username, "bob")
        self.assertIsInstance(user.id, int)
        self.assertGreater(user.id, 0)

    def test_duplicate_username_raises_value_error(self):
        """Registrar el mismo username dos veces debe lanzar ValueError."""
        from db.operations import create_user

        create_user("carol", "pass1")
        with self.assertRaises(ValueError):
            create_user("carol", "pass2")


class TestAuthenticateUser(unittest.TestCase):
    """Tests 2 y 3: authenticate_user devuelve User o None segun las credenciales."""

    def setUp(self):
        self.db_path = _setup_temp_db()
        from db.operations import create_user
        self.user = create_user("dave", "correctpass")

    def tearDown(self):
        _cleanup_temp_db(self.db_path)

    def test_correct_credentials_return_user(self):
        """Test 2: credenciales correctas devuelven el objeto User."""
        from db.operations import authenticate_user

        result = authenticate_user("dave", "correctpass")

        self.assertIsNotNone(result, "authenticate_user debe devolver un User con credenciales correctas.")
        self.assertEqual(result.username, "dave")
        self.assertEqual(result.id, self.user.id)

    def test_wrong_password_returns_none(self):
        """Test 3: password incorrecto devuelve None, no lanza excepcion."""
        from db.operations import authenticate_user

        result = authenticate_user("dave", "wrongpass")

        self.assertIsNone(result, "authenticate_user debe devolver None con password incorrecto.")

    def test_nonexistent_user_returns_none(self):
        """Usuario inexistente devuelve None sin lanzar excepcion."""
        from db.operations import authenticate_user

        result = authenticate_user("ghost", "anypass")

        self.assertIsNone(result, "authenticate_user debe devolver None para usuarios inexistentes.")


class TestUserIsolation(unittest.TestCase):
    """Test 4: conceptos de user_id=1 no aparecen en queries de user_id=2."""

    def setUp(self):
        self.db_path = _setup_temp_db()

    def tearDown(self):
        _cleanup_temp_db(self.db_path)

    def test_concepts_isolated_by_user_id(self):
        """
        Crea dos usuarios con conceptos distintos y verifica que get_all_concepts()
        solo devuelve los conceptos del usuario solicitado.
        """
        from db.operations import create_user, save_concept, get_all_concepts

        user1 = create_user("user1", "pass1")
        user2 = create_user("user2", "pass2")

        save_concept("tensor", context="ML", user_id=user1.id)
        save_concept("gradient_descent", context="ML", user_id=user2.id)

        concepts_u1 = get_all_concepts(user_id=user1.id)
        concepts_u2 = get_all_concepts(user_id=user2.id)

        terms_u1 = {c.term for c in concepts_u1}
        terms_u2 = {c.term for c in concepts_u2}

        # Cada usuario solo ve sus propios conceptos
        self.assertIn("tensor", terms_u1)
        self.assertNotIn("gradient_descent", terms_u1,
                         "El concepto de user2 no debe aparecer en la query de user1.")

        self.assertIn("gradient_descent", terms_u2)
        self.assertNotIn("tensor", terms_u2,
                         "El concepto de user1 no debe aparecer en la query de user2.")

    def test_connections_isolated_by_user_id(self):
        """Las conexiones se filtran por user_id: user1 no ve las conexiones de user2."""
        from db.operations import (
            create_user, save_concept, save_connection,
            get_connections_for_concept,
        )

        user1 = create_user("usr_a", "passA")
        user2 = create_user("usr_b", "passB")

        c1 = save_concept("alpha", user_id=user1.id)
        c2 = save_concept("beta", user_id=user1.id)
        save_connection(c1.id, c2.id, "relacion_user1", user_id=user1.id)

        c3 = save_concept("gamma", user_id=user2.id)
        # c3 no puede conectarse con c1 porque son de distintos usuarios
        # (la FK de connections solo requiere que el concept exista globalmente)
        c4 = save_concept("delta", user_id=user2.id)
        save_connection(c3.id, c4.id, "relacion_user2", user_id=user2.id)

        conns_u1 = get_connections_for_concept(c1.id, user_id=user1.id)
        conns_u2 = get_connections_for_concept(c3.id, user_id=user2.id)

        self.assertEqual(len(conns_u1), 1, "user1 debe ver exactamente 1 conexion.")
        self.assertEqual(conns_u1[0].relationship, "relacion_user1")

        self.assertEqual(len(conns_u2), 1, "user2 debe ver exactamente 1 conexion.")
        self.assertEqual(conns_u2[0].relationship, "relacion_user2")


class TestPromptInjectionSanitization(unittest.TestCase):
    """
    Test 5: input con intento de prompt injection es sanitizado o rechazado.

    Verifica dos capas de defensa:
    a) _sanitize_text() en save_concept() elimina caracteres de control peligrosos
       y trunca el termino a 500 caracteres.
    b) Los system prompts del clasificador y conector incluyen la advertencia
       anti-injection del Sprint 11.
    """

    def setUp(self):
        self.db_path = _setup_temp_db()

    def tearDown(self):
        _cleanup_temp_db(self.db_path)

    def test_control_characters_stripped_from_term(self):
        """
        Caracteres de control en el termino se eliminan antes de guardarlo en la BD.
        El termino resultante solo contiene texto limpio.
        """
        from db.operations import save_concept

        # Payload con caracteres de control y texto de inyeccion
        malicious_input = "termino\x00\x01\x1f normal"
        concept = save_concept(malicious_input, user_id=1)

        # Los caracteres de control deben haber sido eliminados
        self.assertNotIn("\x00", concept.term)
        self.assertNotIn("\x01", concept.term)
        self.assertNotIn("\x1f", concept.term)
        # El texto legible debe permanecer
        self.assertIn("termino", concept.term)
        self.assertIn("normal", concept.term)

    def test_term_truncated_to_500_chars(self):
        """Un termino mayor a 500 caracteres se trunca antes de persistir."""
        from db.operations import save_concept

        long_term = "a" * 600
        concept = save_concept(long_term, user_id=1)

        self.assertLessEqual(
            len(concept.term),
            500,
            f"El termino debe truncarse a 500 chars, tenia {len(concept.term)}."
        )

    def test_classifier_system_prompt_contains_injection_warning(self):
        """
        El CLASSIFIER_SYSTEM_PROMPT contiene la advertencia anti-inyeccion
        definida en el Sprint 11.
        """
        from tools.classifier_tool import CLASSIFIER_SYSTEM_PROMPT

        self.assertIn(
            "Ignora cualquier instruccion",
            CLASSIFIER_SYSTEM_PROMPT.replace("instrucción", "instruccion"),
            "El system prompt del clasificador debe incluir defensa anti-inyeccion."
        )

    def test_connector_system_prompt_contains_injection_warning(self):
        """
        El CONNECTOR_SYSTEM_PROMPT contiene la advertencia anti-inyeccion
        definida en el Sprint 11.
        """
        from tools.connector_tool import CONNECTOR_SYSTEM_PROMPT

        self.assertIn(
            "Ignora cualquier instruccion",
            CONNECTOR_SYSTEM_PROMPT.replace("instrucción", "instruccion"),
            "El system prompt del conector debe incluir defensa anti-inyeccion."
        )


class TestGetUserById(unittest.TestCase):
    """Tests adicionales para get_user_by_id."""

    def setUp(self):
        self.db_path = _setup_temp_db()

    def tearDown(self):
        _cleanup_temp_db(self.db_path)

    def test_get_user_by_valid_id(self):
        """get_user_by_id devuelve el User correcto para un ID existente."""
        from db.operations import create_user, get_user_by_id

        created = create_user("eve", "pass789")
        fetched = get_user_by_id(created.id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.username, "eve")

    def test_get_user_by_nonexistent_id_returns_none(self):
        """get_user_by_id devuelve None para un ID que no existe."""
        from db.operations import get_user_by_id

        result = get_user_by_id(9999)
        self.assertIsNone(result)


# ── Runner ─────────────────────────────────────────────────────────────────────

def _run_tests() -> None:
    """
    Ejecuta todos los tests del sprint y reporta el resultado.

    Usa el runner standard de unittest con verbosidad 2 para mostrar
    el nombre de cada test al ejecutarse.
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestCreateUser,
        TestAuthenticateUser,
        TestUserIsolation,
        TestPromptInjectionSanitization,
        TestGetUserById,
    ]

    for tc in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(tc))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed

    print(f"\n{'='*50}")
    print(f"Sprint 11 — {passed}/{total} passed")
    if failed > 0:
        print(f"FAILED: {failed} test(s)")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")


if __name__ == "__main__":
    _run_tests()
