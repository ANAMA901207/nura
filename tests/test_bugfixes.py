"""
tests/test_bugfixes.py
======================
Harness de regresión para los tres bugs corregidos en el ciclo post-Sprint 11:

Bug 1 — ui/components.py:
    Verificar que ningún campo de texto de Concept usa st.write() o st.text()
    sin unsafe_allow_html=True.

Bug 2 — agents/capture_agent.py (_is_question):
    Frases > 4 palabras que empiezan con 'no entiendo', 'no sé', 'cómo funciona',
    'qué es', 'explícame' etc. deben detectarse como preguntas, no como chat o
    términos.  Inputs > 6 palabras con verbos de oración también.

Bug 3 — agents/capture_agent.py + ui/app.py:
    Cuando un término ya existe con is_classified=True y el usuario lo escribe
    de nuevo, debe retornar mode='reclassify' en lugar de lanzar ValueError.

Todos los tests de bugs 2 y 3 son deterministas (no usan API de Gemini).

Ejecutar con:
    python -m pytest tests/test_bugfixes.py -v
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# BD temporal aislada — se configura ANTES de importar db.schema
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()

import db.schema as _schema
_schema.DB_PATH = Path(_tmp.name)

from db.schema import init_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db():
    """Resetea la BD antes de cada test para garantizar aislamiento."""
    conn = sqlite3.connect(str(_schema.DB_PATH))
    conn.executescript("""
        DROP TABLE IF EXISTS connections;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS daily_summaries;
        DROP TABLE IF EXISTS users;
    """)
    conn.close()
    init_db()


# ── Bug 1: componentes usan st.markdown con unsafe_allow_html=True ────────────

class TestBug1HtmlRendering:
    """
    Verifica que ui/components.py usa st.markdown(texto, unsafe_allow_html=True)
    para todos los campos de texto de Concept y no usa st.write() ni st.text().
    """

    def test_no_st_write_for_concept_fields(self):
        """
        components.py NO debe llamar a st.write() o st.text() con campos de Concept.

        Se verifica leyendo el código fuente en busca de patrones problemáticos:
        st.write(concept.*) o st.text(concept.*).
        """
        components_src = (
            Path(__file__).parent.parent / "ui" / "components.py"
        ).read_text(encoding="utf-8")

        # Patrones que indicarían renderizado incorrecto de HTML
        bad_patterns = [
            "st.write(concept.",
            "st.text(concept.",
            "st.write(f\"",          # f-string directa sin unsafe_allow_html
        ]
        for pattern in bad_patterns:
            assert pattern not in components_src, (
                f"components.py contiene patrón problemático: '{pattern}'. "
                "Todos los campos de Concept deben renderizarse con "
                "st.markdown(texto, unsafe_allow_html=True)."
            )

    def test_analogy_html_escaped_to_prevent_div_regression(self):
        """
        La analogía DEBE pasar por _html.escape() antes de incrustarse en el
        wrapper <div>.

        Sin escapado, si el LLM devuelve un tag estructural (p.ej. </div>) en
        la analogía, el browser lo interpreta como cierre del wrapper y el
        </div> del f-string queda flotando como texto visible — el bug que este
        fix corrige.  El escapado es la defensa correcta.
        """
        components_src = (
            Path(__file__).parent.parent / "ui" / "components.py"
        ).read_text(encoding="utf-8")

        assert "_html.escape(concept.analogy)" in components_src, (
            "concept.analogy debe escaparse con _html.escape() para evitar que "
            "tags estructurales del LLM (como </div>) rompan el wrapper HTML."
        )

    def test_examples_uses_html_div(self):
        """
        El campo examples debe renderizarse en un <div> HTML, no con Markdown **...**.
        """
        components_src = (
            Path(__file__).parent.parent / "ui" / "components.py"
        ).read_text(encoding="utf-8")

        # Patrón problemático anterior: "**Ejemplo en banca:**"
        assert "**Ejemplo en banca:**" not in components_src, (
            "concept.examples debe renderizarse con <div> HTML puro, no con "
            "sintaxis Markdown '**Ejemplo en banca:**' que se mezcla mal con HTML del LLM."
        )

    def test_flashcard_uses_html_div(self):
        """
        Los campos flashcard_front/back deben renderizarse en <div> HTML,
        no con los delimitadores Markdown _ ... _.
        """
        components_src = (
            Path(__file__).parent.parent / "ui" / "components.py"
        ).read_text(encoding="utf-8")

        # Patrón problemático anterior: "_flashcard_front_"
        assert "_{concept.flashcard_front}_" not in components_src, (
            "concept.flashcard_front/back deben renderizarse con <div> HTML, no con "
            "delimitadores Markdown '_ ... _' que pueden romper el renderizado si el "
            "contenido del LLM contiene guiones bajos."
        )


# ── Bug 2: _is_question detecta frases > 4 palabras ──────────────────────────

class TestBug2IsQuestion:
    """
    Verifica que las funciones heurísticas _is_chat e _is_question clasifican
    correctamente los inputs de más de 4 palabras que expresan preguntas.
    """

    def _run(self, text: str) -> str:
        """
        Ejecuta el capture_agent con la BD actual y retorna el modo detectado.
        No usa el grafo completo — solo las funciones de detección puras.
        """
        from agents.capture_agent import _is_chat, _is_quiz, _is_review, _is_question
        if _is_chat(text):
            return "chat"
        if _is_quiz(text):
            return "quiz"
        if _is_review(text):
            return "review"
        if _is_question(text):
            return "question"
        return "capture"

    # ── Frases cortas que deben seguir siendo chat ────────────────────────────

    def test_short_no_entiendo_is_chat(self):
        """'no entiendo' solo (≤ 4 palabras) sigue siendo chat."""
        assert self._run("no entiendo") == "chat"

    def test_no_entiendo_tres_palabras_is_chat(self):
        """'no entiendo nada' (3 palabras, ≤ 4) sigue siendo chat."""
        assert self._run("no entiendo nada") == "chat"

    # ── Frases > 4 palabras que deben ser preguntas ───────────────────────────

    def test_no_entiendo_que_es_five_words(self):
        """'no entiendo qué es blockchain' (5 palabras) → question."""
        assert self._run("no entiendo qué es blockchain") == "question"

    def test_no_se_como_funciona_extended(self):
        """'no sé cómo funciona la regresión logística' → question."""
        assert self._run("no sé cómo funciona la regresión logística") == "question"

    def test_explicame_extended(self):
        """'explícame qué es la tasa de descuento' → question."""
        assert self._run("explícame qué es la tasa de descuento") == "question"

    def test_como_funciona_extended(self):
        """'cómo funciona el algoritmo de spaced repetition' → question."""
        assert self._run("cómo funciona el algoritmo de spaced repetition") == "question"

    def test_que_es_extended(self):
        """'qué es el machine learning exactamente' → question."""
        assert self._run("qué es el machine learning exactamente") == "question"

    def test_no_entiendo_que_es_seven_words(self):
        """'no entiendo qué es el flujo de caja libre' (> 6 palabras) → question."""
        assert self._run("no entiendo qué es el flujo de caja libre") == "question"

    def test_long_sentence_with_verb_funciona(self):
        """Input > 6 palabras con verbo 'funciona' → question."""
        assert self._run("la tasa de mora cómo funciona en la práctica") == "question"

    # ── Términos técnicos que NO deben ser preguntas ──────────────────────────

    def test_technical_term_short_stays_capture(self):
        """'tasa de interés nominal' (4 palabras) → capture."""
        assert self._run("tasa de interés nominal") == "capture"

    def test_technical_term_long_stays_capture(self):
        """'valor presente neto ajustado por riesgo' (6 palabras) → capture."""
        assert self._run("valor presente neto ajustado por riesgo") == "capture"

    # ── Detección con '?' sigue funcionando ──────────────────────────────────

    def test_question_mark_always_question(self):
        """Cualquier input con '?' → question."""
        assert self._run("blockchain?") == "question"
        assert self._run("qué es la tasa de mora?") == "question"


# ── Bug 3: término clasificado escrito de nuevo → reclassify ─────────────────

class TestBug3ReclassifyClassified:
    """
    Verifica que capture_agent retorna mode='reclassify' cuando el término
    ya existe con is_classified=True, en lugar de lanzar ValueError.
    """

    def test_classified_term_returns_reclassify(self):
        """
        Escribir un término ya clasificado activa mode='confirm_reclassify' (Sprint 20),
        en lugar de reclasificar silenciosamente — la UI pregunta al usuario si es el
        mismo concepto o uno diferente.

        Flujo:
        1. Guardar el concepto.
        2. Clasificarlo (update_concept_classification → is_classified=True).
        3. Llamar capture_agent con el mismo término.
        4. Verificar mode='confirm_reclassify' y current_concept no None.
        """
        from db.operations import save_concept, update_concept_classification
        from agents.capture_agent import capture_agent

        # Guardar y clasificar el concepto
        concept = save_concept("blockchain", context="test", user_id=1)
        update_concept_classification(
            concept.id,
            {
                "category": "Tecnología",
                "subcategory": "Blockchain",
                "explanation": "Cadena de bloques distribuida.",
                "examples": "",
                "analogy": "",
                "flashcard_front": "¿Qué es blockchain?",
                "flashcard_back": "Una cadena de bloques distribuida.",
            },
            user_id=1,
        )

        # capture_agent con el mismo término
        result = capture_agent({
            "user_input": "blockchain",
            "user_context": "nuevo contexto",
            "user_id": 1,
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "",
            "quiz_questions": [],
            "sources": [],
        })

        # Sprint 20: término clasificado ahora retorna 'confirm_reclassify'
        # en lugar de 'reclassify' — la UI pregunta al usuario antes de reclasificar.
        assert result.get("mode") == "confirm_reclassify", (
            f"Se esperaba mode='confirm_reclassify', se obtuvo '{result.get('mode')}'. "
            "Escribir un término ya clasificado debe activar confirmación, no reclasificar directo."
        )
        assert result.get("current_concept") is not None, (
            "current_concept debe ser el concepto existente en mode='confirm_reclassify'."
        )

    def test_unclassified_term_still_reclassifies(self):
        """
        Un término sin clasificar (is_classified=False) también activa reclassify.
        Comportamiento sin cambios respecto a sprints anteriores.
        """
        from db.operations import save_concept
        from agents.capture_agent import capture_agent

        save_concept("amortizacion", context="test", user_id=1)

        result = capture_agent({
            "user_input": "amortizacion",
            "user_context": "",
            "user_id": 1,
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "",
            "quiz_questions": [],
            "sources": [],
        })

        assert result.get("mode") == "reclassify", (
            "Término sin clasificar también debe retornar mode='reclassify'."
        )

    def test_new_term_still_captures(self):
        """
        Un término nuevo (no en BD) sigue usando mode='capture'.
        No se regresionó el comportamiento de captura.
        """
        from agents.capture_agent import capture_agent

        result = capture_agent({
            "user_input": "derivado financiero",
            "user_context": "",
            "user_id": 1,
            "current_concept": None,
            "all_concepts": [],
            "new_connections": [],
            "response": "",
            "mode": "",
            "quiz_questions": [],
            "sources": [],
        })

        assert result.get("mode") == "capture", (
            f"Término nuevo debe retornar mode='capture', se obtuvo '{result.get('mode')}'."
        )
        assert result.get("current_concept") is not None

    def test_reclassify_badge_defined_in_app(self):
        """
        ui/app.py define el badge 'reclassify' en _BADGES para que el modo
        se muestre correctamente en el historial de conversación.
        """
        app_src = (
            Path(__file__).parent.parent / "ui" / "app.py"
        ).read_text(encoding="utf-8")
        assert '"reclassify"' in app_src, (
            "ui/app.py debe definir el badge 'reclassify' en _BADGES "
            "para que el modo se muestre en el historial."
        )


# ── Cleanup ───────────────────────────────────────────────────────────────────

def teardown_module(module):  # noqa: ARG001
    """Elimina la BD temporal al terminar todos los tests del módulo."""
    try:
        Path(_tmp.name).unlink()
    except OSError:
        pass  # Windows puede tener el archivo bloqueado; no es un fallo
