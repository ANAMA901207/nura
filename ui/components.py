"""
ui/components.py
================
Funciones auxiliares reutilizables para la interfaz de Nura.

Cada funcion tiene una responsabilidad unica y puede ser invocada
desde ui/app.py de forma independiente.  Las funciones que usan st.*
importan streamlit localmente para facilitar los tests (que mockean
el modulo antes de importar este archivo).

Convencion de retorno
---------------------
- render_concept_card()    → None  (escribe en Streamlit directamente)
- render_flashcard()       → str   (HTML listo para st.markdown o st.html)
- render_knowledge_map()   → str   (HTML completo de pyvis)
- render_daily_summary()   → None  (escribe en Streamlit directamente)
"""

from __future__ import annotations

import html as _html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.models import Concept, Connection, DailySummary

import re

def _strip_html_tags(text: str) -> str:
    """Elimina tags HTML del texto antes de escaparlo."""
    return re.sub(r'<[^>]+>', '', text or '').strip()

# ── paleta de colores por categoria ──────────────────────────────────────────
# Mapeados al tema Catppuccin Mocha para coherencia visual con el fondo oscuro.
CATEGORY_COLORS: dict[str, str] = {
    "finanzas":      "#a6e3a1",  # verde
    "credito":       "#60a0ff",  # azul
    "riesgo":        "#f38ba8",  # rojo
    "contabilidad":  "#f9e2af",  # amarillo
    "economia":      "#cba6f7",  # violeta
    "tecnologia":    "#94e2d5",  # cyan
    "derecho":       "#fab387",  # naranja
    "matematicas":   "#89dceb",  # sky
    "estadistica":   "#b4befe",  # lavanda
}
DEFAULT_NODE_COLOR = "#6c7086"  # overlay0 para categorias desconocidas


def _category_color(category: str) -> str:
    """
    Devuelve el color hex asignado a una categoria.

    La comparacion es case-insensitive y elimina tildes comunes para
    maximizar los matches sin requerir spelling exacto.

    Parametros
    ----------
    category : Nombre de la categoria del concepto.

    Devuelve
    --------
    Color hex como string (p. ej. '#a6e3a1').
    """
    key = (
        category.lower()
        .replace("é", "e").replace("ó", "o").replace("ú", "u")
        .replace("á", "a").replace("í", "i").replace("ñ", "n")
        .strip()
    )
    # Busqueda por prefijo para mayor flexibilidad
    for cat_key, color in CATEGORY_COLORS.items():
        if key.startswith(cat_key) or cat_key.startswith(key):
            return color
    return DEFAULT_NODE_COLOR


# ── render_concept_card ───────────────────────────────────────────────────────

def render_concept_card(
    concept: "Concept",
    show_edit: bool = False,
    show_actions: bool = False,
    card_index: int = 0,
) -> None:
    """
    Renderiza un concepto completo con todas sus capas de conocimiento.

    Muestra en Streamlit: término, categoría/subcategoría, badge de estado
    de clasificación (si is_classified=False muestra ⚠️ Sin clasificar),
    explicación, analogía, ejemplo bancario y flashcard.

    Parametros
    ----------
    concept      : Instancia de Concept con los campos del clasificador.
    show_edit    : Si True, muestra el formulario de corrección rápida de
                   category, subcategory y explanation (usado en el historial).
    show_actions : Si True, muestra botones Editar y Eliminar (Mis conceptos).
    card_index   : Índice único del contexto de renderizado.  Evita claves de
                   formulario duplicadas cuando el mismo concepto aparece
                   varias veces en la misma página.
    """
    import streamlit as st

    is_classified = getattr(concept, "is_classified", True)
    color = _category_color(concept.category) if is_classified else "#f38ba8"
    mastery_pct = concept.mastery_level * 20  # 0-5 → 0-100%

    # Badge de estado de clasificación
    classified_badge = ""
    if not is_classified:
        classified_badge = (
            "<span style='background:#f38ba822; color:#f38ba8; "
            "border:1px solid #f38ba855; border-radius:20px; "
            "padding:2px 10px; font-size:0.72rem; font-weight:700; "
            "margin-left:0.5rem;'>Pendiente</span>"
        )

    # Cabecera: término + badge de categoría + badge de estado
    # La explicación y la analogía se renderizan fuera del bloque HTML para
    # que st.markdown(..., unsafe_allow_html=True) las procese correctamente
    # tanto si el LLM devolvió Markdown como si devolvió etiquetas HTML.
    cat_badge = (
        f"<span style='background:{color}22; color:{color}; border:1px solid {color}55; "
        f"border-radius:20px; padding:2px 10px; font-size:0.75rem; font-weight:600; "
        f"letter-spacing:0.05em;'>{_html.escape(concept.category)}</span>"
        if concept.category else ""
    )
    sub_badge = (
        f"<span style='background:#45475a22; color:#6c7086; border:1px solid #45475a; "
        f"border-radius:20px; padding:2px 8px; font-size:0.7rem;'>"
        f"{_html.escape(concept.subcategory)}</span>"
        if concept.subcategory else ""
    )
    _header_html = (
        f"<div style='background:#313244; border:1px solid #45475a; "
        f"border-left:4px solid {color}; border-radius:12px; "
        f"padding:1.25rem 1.5rem 0.75rem 1.5rem; margin-bottom:0.25rem;'>"
        f"<div style='display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;'>"
        f"<h3 style='margin:0; color:#cdd6f4; font-size:1.2rem; font-weight:700;'>"
        f"{_html.escape(concept.term)}</h3>"
        f"{cat_badge}{sub_badge}{classified_badge}"
        f"</div></div>"
    )

    # Sprint 21: cuando show_actions=True, mostrar el botón Editar inline
    # junto al título de la tarjeta, sin necesidad de abrir un expander primero.
    _edit_state_key = f"_card_edit_{concept.id}_{card_index}"
    if show_actions:
        _hdr_col, _action_col = st.columns([11, 1])
        with _hdr_col:
            st.markdown(_header_html, unsafe_allow_html=True)
        with _action_col:
            if st.button(
                "✏️",
                key=f"edit_btn_{concept.id}_{card_index}",
                help="Editar concepto",
            ):
                st.session_state[_edit_state_key] = not st.session_state.get(
                    _edit_state_key, False
                )
    else:
        st.markdown(_header_html, unsafe_allow_html=True)

    # Explicación — escapa el contenido LLM para evitar que tags estructurales
    # (</div>, </p>) cierren prematuramente el wrapper y aparezcan como texto.
    explanation_text = concept.explanation or ""
    if explanation_text:
        if len(explanation_text) > 300:
            explanation_text = explanation_text[:300] + "…"
        st.markdown(
            f"<div style='color:#a6adc8; font-size:0.9rem; margin:0.4rem 0 0.6rem 0; "
            f"line-height:1.6; padding:0 1.5rem;'>{_html.escape(_strip_html_tags(explanation_text))}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#6c7086; font-size:0.9rem; font-style:italic; "
            "margin:0.4rem 0 0.6rem 0; padding:0 1.5rem;'>Sin explicación aún</div>",
            unsafe_allow_html=True,
        )

    # Analogía — escapada para evitar el bug de </div> visible.
    if concept.analogy:
        st.markdown(
            f"<div style='color:#7f849c; font-size:0.8rem; margin:0 0 0.5rem 0; "
            f"padding:0 1.5rem;'>{_html.escape(concept.analogy)}</div>",
            unsafe_allow_html=True,
        )

    # Detalles expandibles — escapar contenido LLM para evitar tags rotos.
    if concept.examples or concept.flashcard_front:
        with st.expander("Ver ejemplo y flashcard"):
            if concept.examples:
                # Sprint 20: etiqueta dinámica del ejemplo según categoría del concepto
                _cat_lower = (concept.category or "").lower()
                if any(k in _cat_lower for k in ("finanz", "banca", "crédit", "credit", "econom")):
                    _example_label = "Ejemplo en banca"
                elif any(k in _cat_lower for k in ("inteligencia artificial", "machine learning", " ml ", "aprendizaje automático")):
                    _example_label = "Ejemplo en IA"
                elif any(k in _cat_lower for k in ("softwar", "program", "código", "codigo", "desarroll", "tecnolog")):
                    _example_label = "Ejemplo en código"
                elif any(k in _cat_lower for k in ("negoci", "product", "market", "emprend")):
                    _example_label = "Ejemplo en negocio"
                elif any(k in _cat_lower for k in ("diseñ", "experiencia de usuario", "ux design")):
                    _example_label = "Ejemplo en diseño"
                else:
                    _example_label = "Ejemplo práctico"
                st.markdown(
                    f"<div style='color:#a6adc8; font-size:0.875rem; "
                    f"margin-bottom:0.5rem; line-height:1.6;'>"
                    f"<b>{_example_label}:</b> {_html.escape(_strip_html_tags(concept.examples))}</div>",
                    unsafe_allow_html=True,
                )
            if concept.flashcard_front:
                st.markdown(
                    f"<div style='color:#a6adc8; font-size:0.875rem; line-height:1.6;'>"
                    f"<b>Flashcard:</b> {_html.escape(_strip_html_tags(concept.flashcard_front))}"
                    f" <span style='color:#6c7086;'>→</span> "
                    f"<span style='color:#a6e3a1;'>{_html.escape(_strip_html_tags(concept.flashcard_back or ''))}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # Barra de dominio
    if concept.mastery_level > 0:
        st.markdown(
            f"<div style='margin-top:0.25rem;'>"
            f"<div style='font-size:0.7rem; color:#6c7086; margin-bottom:3px;'>Dominio: {concept.mastery_level}/5</div>"
            f"<div style='background:#313244; border-radius:4px; height:4px;'>"
            f"<div style='background:{color}; width:{mastery_pct}%; height:100%; border-radius:4px;'></div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    # Formulario inline (Sprint 21): abre cuando se hace click en ✏️ (show_actions)
    if show_actions and st.session_state.get(_edit_state_key, False):
        with st.expander("Editar concepto", expanded=True):
            with st.form(key=f"edit_concept_{concept.id}_{card_index}"):
                # Sprint 22: campo de nombre del concepto editable
                new_term = st.text_input(
                    "Término",
                    value=concept.term or "",
                    placeholder="Nombre del concepto",
                )
                new_category = st.text_input(
                    "Categoría",
                    value=concept.category or "",
                    placeholder="ej: Finanzas",
                )
                new_subcategory = st.text_input(
                    "Subcategoría",
                    value=concept.subcategory or "",
                    placeholder="ej: Riesgo de crédito",
                )
                new_explanation = st.text_area(
                    "Explicación",
                    value=concept.explanation or "",
                    height=100,
                    placeholder="Describe el concepto en términos simples...",
                )
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.form_submit_button("Guardar", use_container_width=True, type="primary"):
                        from db.operations import update_concept_fields
                        _user_id = getattr(concept, "user_id", 1)
                        update_concept_fields(
                            concept.id,
                            user_id=_user_id,
                            term=new_term.strip() or concept.term,
                            category=new_category.strip(),
                            subcategory=new_subcategory.strip(),
                            explanation=new_explanation.strip(),
                        )
                        st.session_state[_edit_state_key] = False
                        st.success(f"Concepto actualizado.")
                        st.rerun()
                with col_cancel:
                    if st.form_submit_button("Cancelar", use_container_width=True):
                        st.session_state[_edit_state_key] = False
                        st.rerun()

    # Formulario de corrección desde el historial (show_edit)
    if show_edit:
        with st.expander("Editar concepto"):
            with st.form(key=f"edit_concept_{concept.id}_{card_index}"):
                new_category = st.text_input(
                    "Categoría",
                    value=concept.category or "",
                    placeholder="ej: Finanzas",
                )
                new_subcategory = st.text_input(
                    "Subcategoría",
                    value=concept.subcategory or "",
                    placeholder="ej: Riesgo de crédito",
                )
                new_explanation = st.text_area(
                    "Explicación",
                    value=concept.explanation or "",
                    height=100,
                    placeholder="Describe el concepto en términos simples...",
                )
                if st.form_submit_button("Guardar cambios", use_container_width=True):
                    from db.operations import update_concept_classification
                    update_concept_classification(
                        concept.id,
                        {
                            "category":    new_category.strip(),
                            "subcategory": new_subcategory.strip(),
                            "explanation": new_explanation.strip(),
                        },
                    )
                    st.success(f"'{concept.term}' actualizado correctamente.")
                    st.rerun()


# ── render_flashcard ──────────────────────────────────────────────────────────

def render_flashcard(concept: "Concept", show_back: bool = False) -> str:
    """
    Genera el HTML de una flashcard para un concepto dado.

    La flashcard tiene dos caras: frente (pregunta) y reverso (respuesta).
    El parametro show_back controla cual se muestra.  La funcion retorna
    HTML puro para ser renderizado con st.markdown o st.components.v1.html.

    Sprint 7: si consecutive_correct >= 2, muestra un indicador de racha
    '🔥 Racha: N' en la esquina inferior izquierda de la tarjeta para
    motivar al usuario a mantener la racha de aciertos.

    Parametros
    ----------
    concept   : Concepto cuya flashcard se quiere mostrar.
    show_back : Si True, muestra el reverso (respuesta); si False, el frente.

    Devuelve
    --------
    str con el HTML completo de la tarjeta lista para renderizar.
    """
    color = _category_color(concept.category)
    label = "REVERSO" if show_back else "FRENTE"
    label_color = "#f9e2af" if show_back else "#60a0ff"
    content = concept.flashcard_back if show_back else concept.flashcard_front

    # Lucide SVG icons (32px) para cada estado de la tarjeta
    _SVG_BULB = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"'
        ' fill="none" stroke="#f9e2af" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1'
        ' .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>'
    )
    _SVG_QMARK = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"'
        ' fill="none" stroke="#60a0ff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/>'
        '<path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>'
    )
    _SVG_BOOK = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24"'
        ' fill="none" stroke="#a6adc8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
        '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'
    )
    icon = _SVG_BULB if show_back else _SVG_QMARK

    # Si no tiene flashcard generada, muestra el termino y la explicacion
    if not concept.flashcard_front:
        content = concept.explanation[:200] or concept.term
        label = "CONCEPTO"
        label_color = "#a6adc8"
        icon = _SVG_BOOK

    # Escapar el contenido antes de embederlo en HTML: evita que etiquetas
    # generadas por el LLM (p. ej. <div>, <p style=...>) rompan la tarjeta
    # o se muestren como texto crudo cuando el HTML de retorno es renderizado.
    content_safe = _html.escape(content or "—")
    category_safe = _html.escape(concept.category or "—")
    term_safe = _html.escape(concept.term)

    # Indicador de racha (Sprint 7) — visible cuando hay 2+ aciertos consecutivos
    consecutive = getattr(concept, "consecutive_correct", 0)
    streak_html = ""
    if consecutive >= 2:
        streak_html = (
            f"<span style='"
            f"position:absolute; bottom:1rem; left:1.25rem;"
            f"background:#f9e2af22; color:#f9e2af;"
            f"border:1px solid #f9e2af44; border-radius:12px;"
            f"padding:2px 10px; font-size:0.72rem; font-weight:700;"
            f"'>🔥 Racha: {consecutive}</span>"
        )

    return (
        f"<div style='background:linear-gradient(135deg,#313244 0%,#1e1e2e 100%); "
        f"border:1px solid {color}44; border-top:3px solid {color}; border-radius:16px; "
        f"padding:2.5rem 2rem; min-height:200px; display:flex; flex-direction:column; "
        f"justify-content:center; align-items:center; text-align:center; position:relative;'>"
        f"<span style='position:absolute; top:1rem; left:1.25rem; font-size:0.65rem; "
        f"font-weight:700; letter-spacing:0.12em; color:{label_color};'>{label}</span>"
        f"<span style='position:absolute; top:0.85rem; right:1.25rem; background:{color}22; "
        f"color:{color}; border:1px solid {color}44; border-radius:12px; "
        f"padding:1px 8px; font-size:0.7rem;'>{category_safe}</span>"
        f"<div style='font-size:2rem; margin-bottom:0.75rem;'>{icon}</div>"
        f"<p style='color:#cdd6f4; font-size:1.15rem; font-weight:500; "
        f"line-height:1.6; margin:0; max-width:600px;'>{content_safe}</p>"
        f"<p style='color:#45475a; font-size:0.75rem; margin-top:1rem; margin-bottom:0;'>"
        f"{term_safe}</p>"
        f"{streak_html}</div>"
    )


# ── render_knowledge_map ──────────────────────────────────────────────────────

def render_knowledge_map(
    concepts: "list[Concept]",
    connections: "list[Connection]",
    filter_categories: "list[str] | None" = None,
    filter_min_mastery: int = 0,
) -> str:
    """
    Genera el HTML interactivo del mapa de conocimiento con pyvis.

    Cada concepto es un nodo coloreado segun su categoria.  El tamano
    del nodo crece con el mastery_level.  Cada conexion es una arista
    con la etiqueta de la relacion.  Se eliminan aristas duplicadas.

    Los parámetros de filtro se aplican antes de construir el grafo:
    los conceptos que no cumplan ambos criterios desaparecen del mapa
    (y sus aristas también, al no encontrar los nodos extremo).

    El grafo usa fisica Barnes-Hut para un layout organico (springLength=250,
    gravitationalConstant=-6000 para mapas densos).  El HTML generado incluye
    todos los recursos de vis.js via CDN y puede embeberse directamente con
    st.components.v1.html().

    El HTML incluye un listener JavaScript que, al hacer click en un nodo,
    actualiza la URL del padre con history.replaceState (?nura_node=…&view=conectar)
    y hace click en el botón oculto NURA_NODE_SYNC de app.py para un rerun de
    Streamlit sin recargar la página (así no se pierde la sesión de login).
    _init_session() en app.py lee esos query params y rellena map_filter_concept_id.

    Parametros
    ----------
    concepts           : Lista de Concept a representar como nodos.
    connections        : Lista de Connection a representar como aristas.
    filter_categories  : Si se proporciona, solo se muestran conceptos cuya
                         categoria (normalizada) esté en la lista.
                         None o lista vacía = sin filtro de categoría.
    filter_min_mastery : Solo se muestran conceptos con mastery_level >=
                         este valor.  0 = sin filtro (valor por defecto).

    Devuelve
    --------
    str con el HTML completo de la visualizacion interactiva.
    """
    # ── Aplicar filtros ────────────────────────────────────────────────────────
    def _norm(s: str) -> str:
        return (
            s.lower()
            .replace("é", "e").replace("ó", "o").replace("ú", "u")
            .replace("á", "a").replace("í", "i").strip()
        )

    visible = concepts
    if filter_categories:
        norm_filter = {_norm(c) for c in filter_categories}
        visible = [c for c in visible if _norm(c.category) in norm_filter]
    if filter_min_mastery > 0:
        visible = [c for c in visible if c.mastery_level >= filter_min_mastery]
    from pyvis.network import Network

    net = Network(
        height="520px",
        width="100%",
        bgcolor="#1e1e2e",
        font_color="#cdd6f4",
        directed=False,
        notebook=False,
        cdn_resources="remote",
    )

    # Agrega nodos — solo los que pasaron los filtros
    concept_ids = set()
    for concept in visible:
        color = _category_color(concept.category)
        size = 18 + concept.mastery_level * 6  # 18–48 px
        tooltip = (
            f"{concept.category}"
            + (f" / {concept.subcategory}" if concept.subcategory else "")
            + (f"\n{concept.explanation[:120]}..." if len(concept.explanation) > 120
               else f"\n{concept.explanation}" if concept.explanation else "")
        )
        net.add_node(
            concept.id,
            label=concept.term,
            title=tooltip,
            color={"background": color, "border": color, "highlight": {"background": "#cdd6f4", "border": color}},
            size=size,
            font={"size": 13, "color": "#cdd6f4"},
        )
        concept_ids.add(concept.id)

    # Agrega aristas (sin duplicados)
    seen_edges: set[tuple[int, int]] = set()
    for conn in connections:
        a, b = conn.concept_id_a, conn.concept_id_b
        if a not in concept_ids or b not in concept_ids:
            continue
        key = (min(a, b), max(a, b))
        if key in seen_edges:
            continue
        seen_edges.add(key)
        rel_label = conn.relationship[:25] + "..." if len(conn.relationship) > 25 else conn.relationship
        net.add_edge(
            a, b,
            title=conn.relationship,
            label=rel_label,
            color={"color": "#45475a", "highlight": "#60a0ff"},
            width=1.5,
            font={"size": 10, "color": "#7f849c"},
            smooth={"type": "curvedCW", "roundness": 0.2},
        )

    # Opciones de fisica para un layout organico y espaciado
    net.set_options("""{
        "physics": {
            "enabled": true,
            "barnesHut": {
                "gravitationalConstant": -6000,
                "centralGravity": 0.25,
                "springLength": 250,
                "springConstant": 0.04,
                "damping": 0.09
            },
            "minVelocity": 0.75
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 200,
            "navigationButtons": false
        },
        "edges": {
            "smooth": {"enabled": true}
        }
    }""")

    html = net.generate_html()

    # ── Click en nodo → URL con ?nura_node=<id> sin recargar la página ───────────
    # Asignar location.href en la ventana padre recarga el documento; Streamlit
    # resetea session_state en recarga (docs: sesión ligada al WebSocket), lo que
    # cerraba la sesión de login.  Se usa history.replaceState y un click
    # programático al botón oculto nura_map_node_sync en app.py para provocar un
    # rerun conservando la sesión.  _init_session() sigue leyendo nura_node/view.
    _click_script = """
<script>
(function waitForNetwork() {
    if (typeof network !== 'undefined') {
        network.on('click', function(params) {
            if (params.nodes && params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                try {
                    var parentWin = window.parent;
                    var url = new URL(parentWin.location.href);
                    url.searchParams.set('nura_node', String(nodeId));
                    url.searchParams.set('view', 'conectar');
                    parentWin.history.replaceState(null, '', url);
                    var clicked = false;
                    var titleNeedle = 'NURA_MAP_INTERNAL_SYNC_V1';
                    var titled = parentWin.document.querySelectorAll('[title]');
                    var ti, el, t, stb, btn, j, b, txt;
                    for (ti = 0; ti < titled.length; ti++) {
                        el = titled[ti];
                        t = el.getAttribute('title') || '';
                        if (t.indexOf(titleNeedle) !== -1) {
                            stb = el.closest('[data-testid="stButton"]');
                            if (stb) {
                                btn = stb.querySelector('button');
                                if (btn) {
                                    btn.click();
                                    clicked = true;
                                    break;
                                }
                            }
                        }
                    }
                    if (!clicked) {
                        var allBtns = parentWin.document.querySelectorAll('button');
                        for (j = 0; j < allBtns.length; j++) {
                            b = allBtns[j];
                            txt = (b.innerText || b.textContent || '').trim();
                            if (txt === 'NURA_NODE_SYNC') {
                                b.click();
                                clicked = true;
                                break;
                            }
                        }
                    }
                    if (!clicked) {
                        console.warn('Nura: no se pudo sincronizar el mapa (usa el selector de nodos)');
                    }
                } catch(e) {
                    console.warn('Nura: node click sync blocked', e);
                }
            }
        });
    } else {
        setTimeout(waitForNetwork, 150);
    }
})();
</script>
"""
    html = html.replace("</body>", _click_script + "</body>")
    return html


# ── render_concept_detail_panel ───────────────────────────────────────────────

def render_concept_detail_panel(
    concept: "Concept",
    connections_detail: "list[dict]",
) -> None:
    """
    Renderiza el panel de detalle de un concepto seleccionado en el mapa.

    Muestra el nombre del concepto, su categoría, explicación completa y,
    para cada conexión del tipo {'concept': Concept, 'relationship': str},
    una frase legible: '<término> se conecta con <otro término> porque
    <descripción de la relación>'.

    Se usa debajo del mapa de conocimiento cuando el usuario selecciona
    un nodo mediante el selectbox de conceptos visibles.

    Parametros
    ----------
    concept            : El Concept seleccionado por el usuario.
    connections_detail : Lista de dicts de get_concept_connections_detail().
                         Cada dict tiene 'concept' (Concept) y 'relationship' (str).
                         Lista vacía si el concepto no tiene conexiones.
    """
    import streamlit as st

    color = _category_color(concept.category)

    # Cabecera del panel — solo término y badges; la explicación se
    # renderiza aparte con st.markdown(..., unsafe_allow_html=True) para que
    # el texto del LLM (Markdown o HTML) se muestre correctamente.
    cat_badge = (
        f"<span style='background:{color}22; color:{color}; border:1px solid {color}44; "
        f"border-radius:20px; padding:2px 10px; font-size:0.75rem; font-weight:600;'>"
        f"{_html.escape(concept.category)}</span>"
        if concept.category else ""
    )
    sub_badge = (
        f"<span style='color:#6c7086; font-size:0.8rem;'>"
        f"{_html.escape(concept.subcategory)}</span>"
        if concept.subcategory else ""
    )
    st.markdown(
        f"<div style='background:linear-gradient(135deg,#313244 0%,#1e1e2e 100%); "
        f"border:1px solid #45475a; border-left:4px solid {color}; border-radius:12px; "
        f"padding:1.25rem 1.5rem 0.75rem 1.5rem; margin-bottom:0.25rem;'>"
        f"<div style='display:flex; align-items:center; gap:0.75rem; flex-wrap:wrap;'>"
        f"<h4 style='margin:0; color:#cdd6f4; font-size:1.2rem; font-weight:700;'>"
        f"{_html.escape(concept.term)}</h4>{cat_badge}{sub_badge}</div></div>",
        unsafe_allow_html=True,
    )

    # Explicación — escapar para que tags del LLM no rompan el wrapper div.
    explanation_text = concept.explanation or ""
    if explanation_text:
        st.markdown(
            f"<div style='color:#a6adc8; font-size:0.9rem; margin:0.3rem 0 0.75rem 0; "
            f"line-height:1.65; padding:0 1.5rem;'>{_html.escape(explanation_text)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='color:#6c7086; font-size:0.9rem; font-style:italic; "
            "margin:0.3rem 0 0.75rem 0; padding:0 1.5rem;'>Sin explicación aún.</div>",
            unsafe_allow_html=True,
        )

    # Sección de conexiones
    if not connections_detail:
        st.markdown(
            "<p style='color:#6c7086; font-size:0.85rem; font-style:italic;'>"
            "Este concepto aún no tiene conexiones con otros en el mapa.</p>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"<p style='color:#60a0ff; font-size:0.85rem; font-weight:600; margin-bottom:0.5rem;'>"
        f"{len(connections_detail)} conexión(es)</p>",
        unsafe_allow_html=True,
    )
    for item in connections_detail:
        other: "Concept" = item["concept"]
        rel: str = item["relationship"]
        other_color = _category_color(other.category)

        # Frase legible: "TERM se conecta con OTHER porque RELATIONSHIP"
        st.markdown(
            f"<div style='background:#313244; border:1px solid #45475a; border-radius:8px; "
            f"padding:0.65rem 1rem; margin-bottom:0.5rem; font-size:0.875rem; line-height:1.5;'>"
            f"<span style='color:#cdd6f4; font-weight:600;'>{concept.term}</span>"
            f"<span style='color:#6c7086;'> se conecta con </span>"
            f"<span style='color:{other_color}; font-weight:600;'>{other.term}</span>"
            f"<span style='color:#6c7086;'> — </span>"
            f"<span style='color:#a6adc8; font-style:italic;'>{rel or 'relación semántica'}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ── render_sources ────────────────────────────────────────────────────────────

def render_sources(sources: list[dict]) -> None:
    """
    Muestra las fuentes web consultadas por el tutor como lista de links.

    Si la lista esta vacia, la funcion no renderiza nada (no-op).
    Cada fuente se muestra como un link clicable con el titulo de la pagina
    y, debajo, el snippet (resumen) truncado a 120 caracteres.

    Parametros
    ----------
    sources : Lista de dicts con campos title (str), url (str), snippet (str).
              Generada por tutor_agent cuando realizo una busqueda web.

    Nota
    ----
    Se llama desde ui/app.py despues de renderizar la respuesta del tutor,
    solo cuando result.get("sources") es no vacio.
    """
    import streamlit as st

    if not sources:
        return

    st.markdown(
        "<div style='margin-top:0.75rem;'>"
        "<p style='color:#7f849c; font-size:0.78rem; font-weight:700; "
        "letter-spacing:0.05em; text-transform:uppercase; margin-bottom:0.4rem;'>"
        "Fuentes consultadas</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    for src in sources:
        title = src.get("title") or src.get("url", "Fuente")
        url = src.get("url", "")
        snippet = src.get("snippet", "")
        if len(snippet) > 120:
            snippet = snippet[:120] + "..."

        link_html = (
            f"<div style='background:#1e1e2e; border:1px solid #45475a; "
            f"border-left:3px solid #60a0ff; border-radius:6px; "
            f"padding:0.45rem 0.75rem; margin-bottom:0.35rem;'>"
        )
        if url:
            link_html += (
                f"<a href='{url}' target='_blank' "
                f"style='color:#60a0ff; font-size:0.85rem; font-weight:600; "
                f"text-decoration:none;'>{title}</a>"
            )
        else:
            link_html += (
                f"<span style='color:#60a0ff; font-size:0.85rem; "
                f"font-weight:600;'>{title}</span>"
            )
        if snippet:
            link_html += (
                f"<p style='color:#7f849c; font-size:0.78rem; "
                f"margin:0.15rem 0 0 0; line-height:1.4;'>{snippet}</p>"
            )
        link_html += "</div>"
        st.markdown(link_html, unsafe_allow_html=True)


# ── render_daily_summary ──────────────────────────────────────────────────────

def render_daily_summary(summary: "DailySummary") -> None:
    """
    Renderiza el resumen de actividad del dia usando columnas de metricas.

    Muestra tres metricas principales: conceptos capturados, conexiones nuevas
    y conceptos repasados.  Usa st.metric para integrarse con el tema de Streamlit.

    Parametros
    ----------
    summary : Instancia de DailySummary con las metricas del dia actual.
    """
    import streamlit as st

    st.markdown(
        f"""<p style="color:#6c7086; font-size:0.8rem; margin-bottom:0.75rem;">
            {summary.date.strftime("%A %d de %B, %Y")}
        </p>""",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="Conceptos capturados",
            value=summary.concepts_captured,
            delta=None,
            help="Terminos nuevos aprendidos hoy",
        )
    with col2:
        st.metric(
            label="Conexiones nuevas",
            value=summary.new_connections,
            delta=None,
            help="Vinculos semanticos creados hoy",
        )
    with col3:
        st.metric(
            label="Conceptos repasados",
            value=summary.concepts_reviewed,
            delta=None,
            help="Flashcards completadas hoy",
        )


# ── render_quiz ───────────────────────────────────────────────────────────────

def render_quiz(questions: list[dict], quiz_index: int = 0) -> dict:
    """
    Renderiza un quiz interactivo de opcion multiple y devuelve los resultados.

    Muestra todas las preguntas a la vez, cada una con cuatro opciones en radio
    buttons.  Un boton "Responder" revela si cada respuesta fue correcta o no,
    junto con la explicacion del concepto.  Un segundo boton "Guardar resultados"
    registra los resultados via record_flashcard_result y devuelve el dict.

    Usa st.session_state con claves prefijadas por "_quiz_{quiz_index}_" para
    mantener el estado entre reruns.  El parámetro quiz_index garantiza que
    múltiples quizzes en el historial no compartan claves de estado ni de widget.

    Parametros
    ----------
    questions  : Lista de dicts con campos: concept_id (int), question (str),
                 options (list[str] x4), correct_index (int 0-3),
                 explanation (str).
    quiz_index : Índice único del quiz en el contexto de renderizado (ej. el
                 índice de la entrada del historial).  Evita colisiones de keys
                 cuando hay varios quizzes visibles a la vez.

    Devuelve
    --------
    dict[int, bool] con {concept_id: True/False} cuando el usuario
    confirma los resultados.  dict vacio si el quiz no ha terminado aun.
    """
    import streamlit as st
    from db.operations import record_flashcard_result

    if not questions:
        st.info("No hay preguntas disponibles para este quiz.")
        return {}

    # Claves de session_state con sufijo quiz_index para aislar cada instancia
    _fp_key       = f"_quiz_fp_{quiz_index}"
    _answers_key  = f"_quiz_answers_{quiz_index}"
    _revealed_key = f"_quiz_revealed_{quiz_index}"
    _saved_key    = f"_quiz_saved_{quiz_index}"
    _results_key  = f"_quiz_results_{quiz_index}"

    # Fingerprint del quiz actual para detectar si cambiaron las preguntas
    quiz_fp = tuple(q.get("concept_id", i) for i, q in enumerate(questions))

    if st.session_state.get(_fp_key) != quiz_fp:
        st.session_state[_fp_key]       = quiz_fp
        st.session_state[_answers_key]  = {}
        st.session_state[_revealed_key] = False
        st.session_state[_saved_key]    = False
        st.session_state[_results_key]  = {}

    revealed: bool = st.session_state[_revealed_key]
    saved: bool    = st.session_state[_saved_key]

    if saved:
        st.success("Resultados guardados. El dominio de cada concepto fue actualizado.")
        return st.session_state[_results_key]

    # ── Mostrar preguntas ─────────────────────────────────────────────────────
    for i, q in enumerate(questions):
        st.markdown(
            f"<div style='background:#313244; border:1px solid #45475a; "
            f"border-radius:10px; padding:1rem 1.25rem; margin-bottom:0.75rem;'>"
            f"<p style='color:#cba6f7; font-size:0.78rem; font-weight:700; "
            f"margin:0 0 0.25rem 0; text-transform:uppercase; letter-spacing:0.05em;'>"
            f"Pregunta {i + 1}</p>"
            f"<p style='color:#cdd6f4; font-size:0.92rem; margin:0;'>"
            f"{_html.escape(q.get('question', ''))}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

        options = q.get("options", [])
        ci = q.get("correct_index", 0)

        if not revealed:
            sel = st.radio(
                label=f"q_{quiz_index}_{i}",
                options=options,
                key=f"_quiz_radio_{quiz_index}_{i}",
                label_visibility="collapsed",
            )
            if options and sel in options:
                st.session_state[_answers_key][i] = options.index(sel)
        else:
            # Mostrar respuesta del usuario con icono correcto/incorrecto
            user_idx = st.session_state[_answers_key].get(i, -1)
            for j, opt in enumerate(options):
                if j == ci:
                    icon = "✓"
                    color = "#a6e3a1"
                elif j == user_idx and j != ci:
                    icon = "✗"
                    color = "#f38ba8"
                else:
                    icon = " "
                    color = "#7f849c"
                st.markdown(
                    f"<p style='color:{color}; font-size:0.88rem; margin:0.1rem 0;'>"
                    f"{_html.escape(opt)}</p>",
                    unsafe_allow_html=True,
                )
            st.markdown(
                f"<p style='color:#a6adc8; font-size:0.82rem; font-style:italic; "
                f"margin-top:0.4rem;'>{_html.escape(q.get('explanation', ''))}</p>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-bottom:0.25rem;'></div>", unsafe_allow_html=True)

    # ── Botones de accion ─────────────────────────────────────────────────────
    if not revealed:
        if st.button("Responder", type="primary", key=f"_quiz_btn_responder_{quiz_index}"):
            # Rellenar respuestas no seleccionadas con -1
            for i in range(len(questions)):
                if i not in st.session_state[_answers_key]:
                    st.session_state[_answers_key][i] = -1
            st.session_state[_revealed_key] = True
            st.rerun()
    else:
        # Calcular puntaje
        correct_count = sum(
            1 for i, q in enumerate(questions)
            if st.session_state[_answers_key].get(i, -1) == q.get("correct_index", -1)
        )
        total = len(questions)
        pct = int(correct_count / total * 100) if total else 0
        color_score = "#a6e3a1" if pct >= 70 else "#f9e2af" if pct >= 40 else "#f38ba8"
        st.markdown(
            f"<p style='color:{color_score}; font-weight:700; font-size:1rem; "
            f"text-align:center; margin:0.75rem 0;'>"
            f"Puntaje: {correct_count}/{total} ({pct}%)</p>",
            unsafe_allow_html=True,
        )

        if st.button("Guardar resultados", type="primary", key=f"_quiz_btn_guardar_{quiz_index}"):
            results: dict[int, bool] = {}
            for i, q in enumerate(questions):
                cid = q.get("concept_id")
                if cid is None:
                    continue
                is_correct = (
                    st.session_state[_answers_key].get(i, -1) == q.get("correct_index", -1)
                )
                results[cid] = is_correct
                try:
                    record_flashcard_result(cid, correct=is_correct)
                except ValueError:
                    pass  # concept_id invalido — ignorar

            st.session_state[_results_key] = results
            st.session_state[_saved_key]   = True
            st.rerun()

    return st.session_state.get(_results_key, {})


# ── Sprint 12: banner de insight adaptativo ───────────────────────────────────

def render_insight_banner(message: str) -> None:
    """
    Muestra el mensaje generado por insight_agent en un banner destacado.

    El banner tiene fondo azul oscuro, borde izquierdo azul y el ícono 🧠
    para diferenciarlo visualmente del historial de conversación.
    No renderiza nada si el mensaje está vacío.

    Parámetros
    ----------
    message : Texto del insight generado por insight_agent.  Puede contener HTML.
    """
    import streamlit as st

    if not message:
        return

    # v0 reference: bg-card border-l-4 border-l-primary → #313244 + #60a0ff left border
    _sparkles_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24"'
        ' fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936'
        'A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937'
        'l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135'
        'a.5.5 0 0 1-.963 0z"/>'
        '<path d="M20 3v4m2-2h-4M4 17v2m1-1H3"/></svg>'
    )
    st.markdown(
        f"<div style='background:#313244; border:1px solid #45475a; border-left:4px solid #60a0ff; "
        f"border-radius:12px; padding:1rem 1.25rem; margin-bottom:1.25rem;'>"
        f"<div style='display:flex; align-items:flex-start; gap:0.75rem;'>"
        f"<span style='flex-shrink:0; color:#60a0ff; line-height:1; margin-top:2px;'>{_sparkles_svg}</span>"
        f"<div>"
        f"<p style='color:#60a0ff; font-size:0.68rem; font-weight:700; letter-spacing:0.12em; "
        f"text-transform:uppercase; margin:0 0 0.3rem 0;'>Nura dice</p>"
        f"<p style='color:#cdd6f4; font-size:0.875rem; line-height:1.65; margin:0;'>{message}</p>"
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


# ── Sprint 16: banner motivador al final de sesión ────────────────────────────

# Lucide star SVG (16 px) para el banner motivador
_SVG_STAR_BANNER = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 '
    '12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'
    "</svg>"
)


def render_motivational_toast(message: str) -> None:
    """
    Muestra un mensaje motivador como banner HTML flotante con animación CSS.

    El banner aparece en la esquina inferior derecha con posición fixed, dura
    5 segundos y se desvanece con una animación fade-out.  No bloquea la UI.
    No renderiza nada si el mensaje está vacío.

    Parámetros
    ----------
    message : Texto motivador generado por motivator_agent.  Se escapa con
              html.escape() para evitar inyección HTML.
    """
    import streamlit as st
    import html as _h

    if not message:
        return

    msg_safe = _h.escape(message)
    st.markdown(
        f"""
<style>
@keyframes _nura_toast_fade {{
    0%   {{ opacity: 1; transform: translateY(0); }}
    80%  {{ opacity: 1; transform: translateY(0); }}
    100% {{ opacity: 0; transform: translateY(8px); pointer-events: none; }}
}}
._nura_toast_box {{
    position: fixed;
    bottom: 2rem;
    right: 2rem;
    z-index: 9999;
    background: #313244;
    border: 1px solid #60a0ff;
    border-radius: 12px;
    padding: 0.85rem 1.25rem;
    max-width: 320px;
    display: flex;
    align-items: flex-start;
    gap: 0.65rem;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
    animation: _nura_toast_fade 5s ease forwards;
    pointer-events: none;
}}
</style>
<div class="_nura_toast_box">
    <span style="color:#60a0ff; flex-shrink:0; margin-top:1px;">{_SVG_STAR_BANNER}</span>
    <p style="color:#cdd6f4; font-size:0.85rem; line-height:1.55; margin:0;
              font-style:italic;">{msg_safe}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_motivational_banner(message: str) -> None:
    """
    Alias de render_motivational_toast.  Mantenido por compatibilidad con tests.

    Delega en render_motivational_toast que renderiza el banner HTML flotante.
    """
    render_motivational_toast(message)


# ── Sprint 17: diagrama SVG automático ────────────────────────────────────────

def render_diagram(svg_html: str) -> None:
    """
    Renderiza un diagrama SVG generado por diagram_tool.

    Muestra el SVG dentro de un contenedor con padding y borde sutil para
    integrarlo visualmente con el tema de Nura.  No hace nada si svg_html
    está vacío.

    El contenido SVG proviene de _build_svg en diagram_tool, que escapa los
    textos de nodos y aristas internamente, por lo que es seguro embeber
    directamente con unsafe_allow_html=True.

    Parámetros
    ----------
    svg_html : Cadena SVG completa devuelta por generate_diagram_svg().
               Vacía si el diagrama no fue generado o falló.
    """
    import streamlit as st

    if not svg_html or not svg_html.strip():
        return

    st.markdown(
        f"""
        <div style="
            border: 1px solid #45475a;
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-top: 0.75rem;
            background: #1e1e2e;
            overflow-x: auto;
        ">
            {svg_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
