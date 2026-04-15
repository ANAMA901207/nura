"""
tests/test_sprint21.py
======================
Harness del Sprint 21 — UX y diseño.

Verifica:
1. Campo contexto eliminado del formulario Descubrir.
2. Módulo Dominar tiene las secciones clave (cards de acción, resumen, etc.).
3. render_motivational_toast existe y usa st.toast.
4. render_motivational_banner es ahora alias de toast (backward compat).
5. Nombres consistentes: "Pendiente" en badge, "Editar concepto" en expander.
6. Botón editar inline visible cuando show_actions=True.
7. JS de node click usa {nuranodeclick: nodeId} en render_knowledge_map.
8. Listener en _render_view_conectar acepta el nuevo formato.
"""

from __future__ import annotations

import sys
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GOOGLE_API_KEY", "test-key")


# ── 1. Campo contexto eliminado ───────────────────────────────────────────────

class TestContextFieldRemoved(unittest.TestCase):
    """Verifica que el campo contexto opcional ya no aparece en app.py."""

    def test_context_input_removed_from_descubrir(self):
        """El placeholder 'Contexto opcional' no debe estar dentro del formulario."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        # El input de contexto opcional debe haber sido eliminado del form
        self.assertNotIn(
            'placeholder="Contexto opcional',
            content,
            "El campo 'Contexto opcional' no debe estar en la UI principal",
        )

    def test_handle_submit_called_without_user_context_in_form(self):
        """En el submit del formulario, _handle_submit se llama sin user_context explícito."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        descubrir_start = content.find("def _render_view_descubrir")
        descubrir_end = content.find("\ndef ", descubrir_start + 1)
        descubrir_body = content[descubrir_start:descubrir_end]
        # La llamada a _handle_submit en el submit del form no debe pasar user_context
        # (solo se llama con el input del usuario, el contexto viene del perfil)
        self.assertIn("_handle_submit(user_input.strip())", descubrir_body)


# ── 2. Módulo Dominar — secciones clave ──────────────────────────────────────

class TestDominarLayout(unittest.TestCase):
    """Verifica que _render_view_dominar tiene las secciones del nuevo layout."""

    def _get_dominar_body(self) -> str:
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        start = content.find("def _render_view_dominar")
        end = content.find("\ndef _render_view_conectar", start)
        return content[start:end]

    def test_has_action_cards_section(self):
        """Debe existir la sección de cards de acción rápida."""
        body = self._get_dominar_body()
        self.assertIn("Repasar hoy", body)
        self.assertIn("Quiz rápido", body)

    def test_has_daily_summary_section(self):
        """Debe tener la sección de Resumen de hoy."""
        body = self._get_dominar_body()
        self.assertIn("Resumen de hoy", body)

    def test_has_flashcards_section(self):
        """Debe tener la sección de Flashcards."""
        body = self._get_dominar_body()
        self.assertIn("Flashcards", body)

    def test_concepts_collapsed_by_default(self):
        """Las categorías de conceptos deben estar en expanders con expanded=False."""
        body = self._get_dominar_body()
        self.assertIn("expanded=False", body)

    def test_has_separators(self):
        """Debe tener separadores (st.markdown('---'))."""
        body = self._get_dominar_body()
        self.assertGreaterEqual(body.count('st.markdown("---")'), 3)


# ── 3 & 4. render_motivational_toast + backward compat ───────────────────────

class TestMotivationalToast(unittest.TestCase):
    """Verifica que el toast es la implementación principal."""

    def test_render_motivational_toast_exists(self):
        """render_motivational_toast debe estar definida en components.py."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("def render_motivational_toast", content)

    def test_render_motivational_toast_uses_st_markdown(self):
        """Sprint 22: render_motivational_toast usa st.markdown (banner HTML flotante)."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        start = content.find("def render_motivational_toast")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        self.assertIn("st.markdown", body)
        self.assertIn("position: fixed", body)

    def test_render_motivational_toast_calls_st_markdown(self):
        """Al llamar render_motivational_toast, debe invocar st.markdown con HTML."""
        with patch("streamlit.markdown") as mock_md:
            from importlib import reload
            import ui.components as comp
            reload(comp)
            comp.render_motivational_toast("Buen trabajo hoy!")
            mock_md.assert_called()
            rendered = str(mock_md.call_args)
            self.assertIn("Buen trabajo hoy!", rendered)

    def test_render_motivational_toast_html_escaped(self):
        """El contenido del mensaje se escapa — no hay riesgo de inyección HTML."""
        calls = []
        with patch("streamlit.markdown", side_effect=lambda html, **kw: calls.append(html)):
            from importlib import reload
            import ui.components as comp
            reload(comp)
            comp.render_motivational_toast("<script>alert(1)</script>")
        self.assertTrue(calls)
        self.assertNotIn("<script>alert(1)</script>", calls[0])

    def test_render_motivational_toast_empty_message_no_call(self):
        """Mensaje vacío no debe llamar a st.markdown."""
        with patch("streamlit.markdown") as mock_md:
            from importlib import reload
            import ui.components as comp
            reload(comp)
            comp.render_motivational_toast("")
            mock_md.assert_not_called()

    def test_render_motivational_banner_still_works(self):
        """render_motivational_banner debe seguir existiendo (backward compat)."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("def render_motivational_banner", content)

    def test_render_motivational_banner_delegates_to_toast(self):
        """render_motivational_banner debe delegar a render_motivational_toast (st.markdown)."""
        calls = []
        with patch("streamlit.markdown", side_effect=lambda html, **kw: calls.append(html)):
            from importlib import reload
            import ui.components as comp
            reload(comp)
            comp.render_motivational_banner("Otro día, otro nodo.")
        self.assertTrue(calls, "st.markdown debe invocarse vía banner")


# ── 5. Nombres consistentes ───────────────────────────────────────────────────

class TestConsistentNames(unittest.TestCase):
    """Verifica que los textos de la UI usan los nombres correctos."""

    def test_badge_says_pendiente_not_sin_clasificar(self):
        """El badge de concepto no clasificado debe decir 'Pendiente', no 'Sin clasificar'."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("Pendiente", content)
        self.assertNotIn(">Sin clasificar<", content)

    def test_edit_expander_says_editar_concepto(self):
        """El expander de edición debe llamarse 'Editar concepto'."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("Editar concepto", content)
        # No debe decir "Corregir clasificación" (el término anterior)
        self.assertNotIn("Corregir clasificación", content)

    def test_default_view_is_descubrir(self):
        """El session_state default de current_view debe ser 'descubrir', no 'chat'."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        self.assertNotIn('get("current_view", "chat")', content)
        self.assertIn('get("current_view", "descubrir")', content)


# ── 6. Botón editar inline ────────────────────────────────────────────────────

class TestInlineEditButton(unittest.TestCase):
    """Verifica que el botón editar es inline cuando show_actions=True."""

    def test_edit_button_key_uses_edit_btn_prefix(self):
        """El botón de edición inline debe usar la clave 'edit_btn_'."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("edit_btn_", content)

    def test_show_actions_triggers_columns(self):
        """Con show_actions=True, se usan columnas para mostrar header + edit button."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        # In render_concept_card there should be st.columns for the action layout
        card_start = content.find("def render_concept_card")
        card_end = content.find("\ndef ", card_start + 1)
        card_body = content[card_start:card_end]
        self.assertIn("show_actions", card_body)
        self.assertIn("st.columns", card_body)

    def test_edit_state_key_in_card(self):
        """El estado de apertura del form usa una clave con el ID del concepto."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("_card_edit_", content)
        self.assertIn("_edit_state_key", content)


# ── 7. JS node click usa {nuranodeclick: nodeId} ─────────────────────────────

class TestNodeClickJS(unittest.TestCase):
    """Verifica que el JS en render_knowledge_map usa el nuevo formato."""

    def test_click_event_used_in_knowledge_map(self):
        """render_knowledge_map debe usar network.on('click', ...) para el click."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        km_start = content.find("def render_knowledge_map")
        km_end = content.find("\ndef ", km_start + 1)
        km_body = content[km_start:km_end]
        self.assertIn("network.on('click'", km_body)

    def test_node_click_avoids_full_page_reload(self):
        """El click en nodo debe usar replaceState (no location.href) para no perder la sesión."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        self.assertIn("nura_node", content)
        self.assertIn("history.replaceState", content)
        self.assertNotIn("window.parent.location.href", content)

    def test_conectar_has_hidden_map_sync_button(self):
        """_render_view_conectar incluye el botón puente para el sync del mapa."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        start = content.find("def _render_view_conectar")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        self.assertIn("nura_map_node_sync", body)
        self.assertIn("NURA_MAP_INTERNAL_SYNC_V1", body)

    def test_conectar_uses_selectbox_filter(self):
        """Sprint 22: _render_view_conectar usa selectbox Streamlit para filtrar el mapa."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        start = content.find("def _render_view_conectar")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        # Selectbox nativo como mecanismo principal de filtrado
        self.assertIn("st.selectbox", body)
        self.assertIn("map_filter_concept_id", body)


# ── 8. render_knowledge_map devuelve HTML no vacío ───────────────────────────

class TestKnowledgeMapStillWorks(unittest.TestCase):
    """Verifica que render_knowledge_map sigue funcionando tras los cambios."""

    def test_render_knowledge_map_returns_nonempty_html(self):
        """render_knowledge_map con un concepto debe retornar HTML no vacío."""
        from unittest.mock import MagicMock
        concept = MagicMock()
        concept.id = 1
        concept.term = "LangGraph"
        concept.category = "IA"
        concept.mastery_level = 2
        from ui.components import render_knowledge_map
        result = render_knowledge_map([concept], [])
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)
        self.assertIn("nura_node", result)


# ── 9. Editar término del concepto ───────────────────────────────────────────

class TestEditTermField(unittest.TestCase):
    """Verifica que el formulario inline permite editar el nombre del concepto."""

    def test_term_field_in_show_actions_form(self):
        """El formulario de show_actions debe incluir un campo 'Término'."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        start = content.find("def render_concept_card")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        self.assertIn('"Término"', body)

    def test_show_actions_form_uses_update_concept_fields(self):
        """El formulario inline debe usar update_concept_fields (acepta term)."""
        comp_path = ROOT / "ui" / "components.py"
        content = comp_path.read_text(encoding="utf-8")
        start = content.find("def render_concept_card")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        self.assertIn("update_concept_fields", body)

    def test_update_concept_fields_accepts_term(self):
        """update_concept_fields debe aceptar el campo term sin ValueError."""
        from db.schema import init_db
        from db.operations import save_concept, update_concept_fields
        import tempfile, os
        db_path = ROOT / "db" / "nura.db"
        init_db()
        concept = save_concept("término_test_edit", context="test", user_id=999)
        updated = update_concept_fields(concept.id, user_id=999, term="término_editado")
        self.assertEqual(updated.term, "término_editado")


# ── 10. Selectbox encima del mapa ─────────────────────────────────────────────

class TestSelectboxAboveMap(unittest.TestCase):
    """Verifica que el filtro del mapa usa selectbox encima del mapa."""

    def test_no_postmessage_bridge_in_conectar(self):
        """No debe haber la implementación del bridge postMessage en _render_view_conectar."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        start = content.find("def _render_view_conectar")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        # El bridge oculto ha sido eliminado
        self.assertNotIn("_nura_map_bridge_", body)

    def test_selectbox_before_map_render(self):
        """El selectbox debe aparecer antes de st.components.v1.html en la función."""
        app_path = ROOT / "ui" / "app.py"
        content = app_path.read_text(encoding="utf-8")
        start = content.find("def _render_view_conectar")
        end = content.find("\ndef ", start + 1)
        body = content[start:end]
        sel_pos = body.find("st.selectbox")
        map_pos = body.find("st.components.v1.html")
        self.assertLess(sel_pos, map_pos, "El selectbox debe aparecer antes del mapa")


if __name__ == "__main__":
    unittest.main(verbosity=2)
