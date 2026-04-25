"""
ui/app.py
=========
Aplicacion principal de Nura — interfaz Streamlit en dos tabs.

TAB 1: Chat de captura
    Caja de texto donde el usuario escribe términos, preguntas o solicitudes de repaso.
    Cada submission invoca el grafo LangGraph y muestra la tarjeta
    de concepto enriquecida, la respuesta del tutor o el plan de repaso.
    El historial de la sesión persiste en st.session_state.
    Botón "Sesión de repaso" para iniciar el modo review directamente.

TAB 2: App de aprendizaje
    - Resumen del día: métricas de hoy (conceptos, conexiones, repasos).
    - Mis conceptos: tabla agrupada por categoría.
    - Flashcards: una tarjeta a la vez con botón Voltear y Siguiente.
    - Mapa de conocimiento: grafo interactivo pyvis embebido en HTML.

Ejecutar con:
    streamlit run ui/app.py
desde la raiz del proyecto.
"""

from __future__ import annotations

import sys
import os
import html as _html
import concurrent.futures
from pathlib import Path

# Pillow Image for the custom favicon (loaded once at module level)
def _load_favicon():
    favicon_path = Path(__file__).parent.parent / "design" / "nura_favicon.png"
    if favicon_path.exists():
        try:
            from PIL import Image
            return Image.open(favicon_path)
        except Exception:
            pass
    return "⭐"

_FAVICON = _load_favicon()

# Garantiza que los imports de db/, agents/, ui/ funcionen
# independientemente de desde donde se ejecute Streamlit.
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import streamlit as st
from datetime import date

from db.schema import init_db
from db.operations import (
    delete_concept,
    get_all_concepts,
    get_all_connections,
    get_concept_by_id,
    get_concept_connections_detail,
    get_concepts_due_today,
    get_daily_goal,
    get_dominated_concepts,
    get_mastery_by_category,
    get_neglected_concepts,
    get_reminder_time,
    set_reminder_time,
    get_or_create_daily_summary,
    get_streak,
    get_today_count,
    get_unclassified_concepts,
    get_weekly_insight_data,
    record_flashcard_result,
    update_daily_goal,
    update_daily_summary,
)
from agents.graph import build_graph
from ui.auth import render_login_page, render_onboarding, is_session_valid, refresh_session
from ui.components import (
    render_concept_card,
    render_concept_detail_panel,
    render_daily_summary,
    render_diagram,
    render_flashcard,
    render_insight_banner,
    render_knowledge_map,
    render_motivational_banner,   # kept for backward compat; delegates to toast
    render_motivational_toast,
    render_quiz,
    render_sources,
    render_streak,
)

# ── Design tokens (v0 reference) ──────────────────────────────────────────────
# Primary:    #60a0ff   (Nura blue — N bold, active states, borders, links)
# Background: #1e1e2e   (base dark layer)
# Surface:    #313244   (cards, inputs, sidebar items)
# Border:     #45475a   (subtle dividers)
# Text:       #cdd6f4   (main readable text)
# Muted:      #6c7086   (secondary text, labels)
# Success:    #a6e3a1   (green mastery / correct answers)
# Warning:    #f9e2af   (yellow / quiz)
# Error:      #f38ba8   (red / incorrect)
# Purple:     #cba6f7   (reclassify / review)
# Teal:       #74c7ec   (sky / connections)
# Orange:     #fab387   (streak flame accent)

# ── NuraLogo inline HTML ───────────────────────────────────────────────────────
# Replicates the v0 NuraLogo component: bold N in primary blue + constellation
# SVG of 5 coloured dots connected by thin lines + "Nura" text + subtitle.
_NURA_LOGO_HTML = """
<div style="display:flex;flex-direction:column;align-items:flex-start;
            padding:1.25rem 0 1rem 0;">
  <div style="display:flex;align-items:center;gap:4px;">
    <span style="font-size:2.4rem;font-weight:900;color:#60a0ff;
                 line-height:1;font-family:'Segoe UI',system-ui,sans-serif;">N</span>
    <svg width="36" height="30" viewBox="0 0 32 28" fill="none"
         style="margin-left:2px;margin-bottom:2px;">
      <!-- thin grey connection lines -->
      <line x1="4"  y1="14" x2="12" y2="8"  stroke="#6c7086" stroke-width="0.7"/>
      <line x1="12" y1="8"  x2="22" y2="12" stroke="#6c7086" stroke-width="0.7"/>
      <line x1="22" y1="12" x2="28" y2="6"  stroke="#6c7086" stroke-width="0.7"/>
      <line x1="12" y1="8"  x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
      <line x1="22" y1="12" x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
      <!-- colourful nodes: yellow, purple, green, teal, pink -->
      <circle cx="4"  cy="14" r="2.5" fill="#f9e2af"/>
      <circle cx="12" cy="8"  r="3"   fill="#cba6f7"/>
      <circle cx="22" cy="12" r="2.5" fill="#a6e3a1"/>
      <circle cx="28" cy="6"  r="2"   fill="#74c7ec"/>
      <circle cx="16" cy="20" r="2.5" fill="#f38ba8"/>
    </svg>
  </div>
  <span style="font-size:1.05rem;font-weight:600;color:#cdd6f4;
               margin-top:-4px;letter-spacing:0.01em;">Nura</span>
  <span style="font-size:0.6rem;color:#6c7086;letter-spacing:0.12em;
               margin-top:3px;text-transform:lowercase;">
    aprende · conecta · domina
  </span>
</div>
"""

# ── CSS global ────────────────────────────────────────────────────────────────
_CSS = """
<style>
/* ── Base ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header[data-testid="stHeader"] { height: 2.5rem; }

/* ── Sidebar overrides ── */
[data-testid="stSidebar"] {
    background: #1e1e2e !important;
    border-right: 1px solid #313244 !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}
/* Hide default sidebar collapse arrow — handled by our layout */
[data-testid="stSidebarCollapseButton"] { display: none !important; }

/* ── Tabs ── */
[data-testid="stTabs"] button {
    font-weight: 600;
    letter-spacing: 0.03em;
    font-size: 0.88rem;
    color: #6c7086;
    border-radius: 8px 8px 0 0;
    transition: color 0.15s;
}
[data-testid="stTabs"] button:hover { color: #cdd6f4; }
[data-testid="stTabs"] button[aria-selected="true"] {
    border-bottom: 2px solid #60a0ff !important;
    color: #60a0ff !important;
}

/* ── Text inputs ── */
[data-testid="stTextInput"] input {
    border-radius: 10px;
    border: 1px solid #45475a;
    background: #313244;
    padding: 0.6rem 1rem;
    font-size: 0.95rem;
    color: #cdd6f4;
}
[data-testid="stTextInput"] input:focus {
    border-color: #60a0ff;
    box-shadow: 0 0 0 2px #60a0ff22;
}
[data-testid="stTextInput"] input::placeholder { color: #6c7086; }

/* ── Buttons ── */
[data-testid="baseButton-primary"], .stButton > button {
    border-radius: 8px;
    font-weight: 600;
    letter-spacing: 0.02em;
    border: 1px solid #60a0ff33;
    transition: all 0.15s ease;
}
.stButton > button:hover {
    border-color: #60a0ff;
    box-shadow: 0 0 8px #60a0ff33;
}
/* Sidebar logout button: subtler */
[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    border: 1px solid #45475a;
    color: #6c7086;
    font-size: 0.85rem;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #313244;
    color: #cdd6f4;
    border-color: #60a0ff44;
}
/* Conectar / mapa: botón puente para sync sin recarga (st.button no tiene label_visibility) */
.st-key-nura_map_node_sync {
    position: absolute !important;
    left: -9999px !important;
    top: 0 !important;
    width: 1px !important;
    height: 1px !important;
    padding: 0 !important;
    margin: 0 !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    border: 0 !important;
    white-space: nowrap !important;
}
/* Sidebar nav buttons (inside stColumns): borderless, text-left */
[data-testid="stSidebar"] [data-testid="stColumns"] .stButton > button {
    background: transparent !important;
    border: none !important;
    color: #6c7086 !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    box-shadow: none !important;
    padding: 0.4rem 0.5rem !important;
    letter-spacing: 0 !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stColumns"] .stButton > button:hover {
    background: #313244 !important;
    color: #cdd6f4 !important;
    border-color: transparent !important;
    box-shadow: none !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 12px;
    padding: 1rem;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    border: 1px solid #45475a !important;
    border-radius: 12px !important;
    background: #313244 !important;
}

/* ── Select boxes ── */
[data-testid="stSelectbox"] > div > div {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 10px;
    color: #cdd6f4;
}

/* ── Multiselect ── */
[data-testid="stMultiSelect"] > div > div {
    background: #313244;
    border: 1px solid #45475a;
    border-radius: 10px;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: #60a0ff;
}

/* ── Progress / bar chart ── */
[data-testid="stProgress"] > div > div { background: #60a0ff; }

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #60a0ff; }

/* ── Separator ── */
hr { border-color: #45475a; margin: 1.5rem 0; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* ── Radio buttons ── */
[data-testid="stRadio"] label { color: #cdd6f4; }
</style>
"""


# ── helpers internos ──────────────────────────────────────────────────────────

def _extract_text(value: object) -> str:
    """
    Extrae texto legible de cualquier tipo que pueda devolver LangChain/LangGraph.

    LangChain puede devolver el campo 'response' como:
    - str                       → devolver directamente
    - list[dict]                → extraer 'text'/'content' del primer elemento
    - list[str]                 → unir con espacio
    - list[AIMessage/obj]       → recursar sobre el primer elemento
    - dict                      → extraer 'text' o 'content'
    - AIMessage(content=str)    → devolver content directamente
    - AIMessage(content=list)   → recursar sobre content (puede ser list de bloques)

    La función es recursiva para manejar content blocks anidados.
    Siempre devuelve un str seguro para renderizar en la UI.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        # Detectar si la cadena es la repr de una lista de content-blocks
        # (e.g. "[{'type': 'text', 'text': '...', 'extras': {...}}]")
        # causada por str(response.content) cuando content es una lista.
        stripped = value.strip()
        if stripped.startswith("[{") and ("'text'" in stripped or '"text"' in stripped):
            import ast
            try:
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, list):
                    return _extract_text(parsed)
            except Exception:
                pass
        return value
    if isinstance(value, list):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, str):
            # Lista de strings — unir todas
            return " ".join(str(v) for v in value if v)
        if isinstance(first, dict):
            # Content block: {"type": "text", "text": "..."} o {"content": "..."}
            text = first.get("text") or first.get("content")
            return str(text) if text else str(first)
        # AIMessage u objeto — recursar
        return _extract_text(first)
    if isinstance(value, dict):
        text = value.get("text") or value.get("content")
        return str(text) if text else str(value)
    # AIMessage u otro objeto LangChain con .content
    content = getattr(value, "content", None)
    if content is not None:
        # Recursar: content puede ser str, list de bloques, etc.
        return _extract_text(content)
    return str(value)


def _current_user_id() -> int:
    """
    Devuelve el ID del usuario actualmente autenticado en la sesión.

    Lee el objeto User almacenado en st.session_state['user'] por render_login_page().
    Si por algún motivo no existe (tests unitarios, primeros reruns), devuelve 1
    como usuario legacy de compatibilidad.

    Devuelve
    --------
    int — ID del usuario activo o 1 si no hay usuario en sesión.
    """
    user = st.session_state.get("user")
    return user.id if user is not None else 1

@st.cache_resource
def _get_graph():
    """
    Construye y cachea el grafo LangGraph para la sesion de Streamlit.

    El grafo es costoso de construir (importa modelos, crea el StateGraph).
    st.cache_resource garantiza que se construye una sola vez por proceso
    de servidor, no en cada rerun de la UI.
    """
    return build_graph()


def _empty_state(
    user_input: str,
    user_context: str = "",
    user_id: int = 1,
    mode: str = "",
    user_profile: dict = {},
) -> dict:
    """
    Crea el estado inicial para invocar el grafo con un input dado.

    Parametros
    ----------
    user_input    : Texto del usuario (termino o pregunta).
    user_context  : Contexto adicional opcional ingresado por el usuario.
    user_id       : ID del usuario autenticado (Sprint 11; default=1).
    mode          : Modo pre-establecido.  Usado en Sprint 12 para invocar
                    directamente con mode='insight' sin input del usuario.
    user_profile  : Sprint 15.  Perfil del usuario {profession, learning_area,
                    tech_level}.  Pasado a classifier_agent y tutor_agent para
                    personalizar los prompts.

    Devuelve
    --------
    dict compatible con NuraState listo para graph.invoke().
    """
    return {
        "user_input":             user_input,
        "user_context":           user_context,
        "current_concept":        None,
        "all_concepts":           [],
        "new_connections":        [],
        "response":               "",
        "mode":                   mode,
        "user_id":                user_id,
        "quiz_questions":         [],
        "sources":                [],
        "insight_message":        "",
        "clarification_options":  [],   # Sprint 14
        "spelling_suggestion":    "",   # Sprint 14
        "user_profile":           user_profile,  # Sprint 15
        "diagram_svg":            "",   # Sprint 17
        "suggested_concepts":     [],   # Sprint 18
    }


def _init_session() -> None:
    """
    Inicializa las claves de st.session_state si no existen.

    Se llama al inicio de cada rerun para asegurar que el estado
    de la sesion siempre tenga las claves necesarias.
    """
    if "history" not in st.session_state:
        st.session_state.history = []        # lista de dicts {input, result}
    if "fc_show_back" not in st.session_state:
        st.session_state.fc_show_back = False
    if "fc_queue" not in st.session_state:
        st.session_state.fc_queue = []       # lista de concept_ids en la cola activa
    if "fc_results" not in st.session_state:
        st.session_state.fc_results = {}     # {concept_id: {correct, incorrect, level_before, level_after}}
    if "fc_session_done" not in st.session_state:
        st.session_state.fc_session_done = False
    # Sprint 12: insight diario — solo se genera una vez por día por sesión
    if "insight_message" not in st.session_state:
        st.session_state.insight_message = ""
    if "insight_date" not in st.session_state:
        st.session_state.insight_date = None
    # Vista activa: 'descubrir' | 'dominar' | 'conectar'
    if "current_view" not in st.session_state:
        st.session_state.current_view = "descubrir"
    # Sprint 14: filtro de nodo en mapa Conectar
    if "map_filter_concept_id" not in st.session_state:
        st.session_state.map_filter_concept_id = None
    # Sprint 15: perfil del usuario para personalizar prompts
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {}

    # ── Restaurar estado desde parámetros de URL ─────────────────────────────
    # Cuando el JS de pyvis navega a ?nura_node=<id>&view=conectar (por click
    # en un nodo), Streamlit recarga la app.  Leemos los params aquí para
    # reconstruir el filtro de mapa y la vista activa antes de renderizar nada.
    _qp_node = st.query_params.get("nura_node")
    _qp_view = st.query_params.get("view")
    if _qp_node or _qp_view:
        if _qp_node:
            try:
                st.session_state.map_filter_concept_id = int(_qp_node)
            except (ValueError, TypeError):
                pass
        if _qp_view in ("descubrir", "dominar", "conectar"):
            st.session_state.current_view = _qp_view
        # Limpiar los params de la URL sin recargar (solo actualiza la URL del navegador)
        st.query_params.clear()


_GRAPH_TIMEOUT_SECONDS = 60

_TIMEOUT_RESULT = {
    "user_input":           "",
    "current_concept":      None,
    "all_concepts":         [],
    "new_connections":      [],
    "response":             "Nura está ocupada ahora, intenta en unos minutos 🌙",
    "mode":                 "timeout",
    "quiz_questions":       [],
    "sources":              [],
    "insight_message":      "",
    "diagram_svg":          "",   # Sprint 17
    "suggested_concepts":   [],   # Sprint 18
}


def _invoke_with_timeout(
    user_input: str,
    user_context: str = "",
    user_id: int = 1,
    mode: str = "",
    user_profile: dict = {},
) -> dict:
    """
    Invoca el grafo LangGraph con un timeout de _GRAPH_TIMEOUT_SECONDS segundos.

    Ejecuta graph.invoke() en un hilo separado y espera hasta el límite.
    Si el tiempo se agota, cancela la espera y devuelve _TIMEOUT_RESULT en
    lugar de bloquear la UI indefinidamente.

    Parámetros
    ----------
    user_input    : Texto del usuario ya limpio, pasado al estado inicial del grafo.
    user_context  : Contexto adicional opcional del usuario (Sprint 5).
    user_id       : ID del usuario autenticado (Sprint 11; default=1).
    mode          : Modo pre-establecido para el grafo.  Usado en Sprint 12 para
                    invocar directamente con mode='insight' desde la UI sin input.
    user_profile  : Sprint 15.  Perfil del usuario para personalizar los prompts
                    de clasificación y tutoría.

    Devuelve
    --------
    dict con el resultado del grafo, o _TIMEOUT_RESULT si se agotó el tiempo.
    """
    graph = _get_graph()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            graph.invoke,
            _empty_state(user_input, user_context, user_id, mode, user_profile),
        )
        try:
            return future.result(timeout=_GRAPH_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            return _TIMEOUT_RESULT
        except Exception as exc:
            # Captura cualquier excepcion no manejada que escape del grafo
            # (p.ej. errores de red inesperados) y la convierte en respuesta amigable.
            err_msg = str(exc)
            err_upper = err_msg.upper()
            if any(
                t in err_upper
                for t in ("403", "PERMISSION_DENIED", "API_KEY_INVALID",
                          "SERVICE_DISABLED", "FORBIDDEN", "INVALID API KEY")
            ):
                friendly = (
                    "No puedo conectarme al servicio de IA. "
                    "Verifica que GOOGLE_API_KEY en el archivo .env sea válida "
                    "y que la API de Gemini esté habilitada en tu proyecto de Google Cloud."
                )
            else:
                friendly = f"Ocurrió un error inesperado: {err_msg[:300]}"
            return {**_TIMEOUT_RESULT, "response": friendly, "mode": "error"}


def _handle_submit(user_input: str, user_context: str = "") -> None:
    """
    Procesa el input del usuario: invoca el grafo con timeout y actualiza el historial.

    Si el grafo captura un termino nuevo, actualiza el DailySummary.
    Si hay conexiones nuevas, tambien las contabiliza en el resumen.
    Si el grafo tarda más de 30 s, almacena un resultado de timeout amigable.

    Parametros
    ----------
    user_input   : Texto ingresado por el usuario, ya limpio.
    user_context : Contexto adicional opcional (Sprint 5).
    """
    uid = _current_user_id()
    result = _invoke_with_timeout(
        user_input,
        user_context,
        user_id=uid,
        user_profile=st.session_state.get("user_profile", {}),
    )

    # Actualizar métricas del día — filtradas por usuario (Sprint 11)
    today = date.today()
    if result.get("mode") == "capture":
        summary = get_or_create_daily_summary(today, user_id=uid)
        update_daily_summary(
            today,
            user_id=uid,
            concepts_captured=summary.concepts_captured + 1,
        )
        n_conn = len(result.get("new_connections") or [])
        if n_conn > 0:
            summary = get_or_create_daily_summary(today, user_id=uid)
            update_daily_summary(
                today,
                user_id=uid,
                new_connections=summary.new_connections + n_conn,
            )

    st.session_state.history.insert(0, {"input": user_input, "result": result})


# ── Vista: Descubrir ──────────────────────────────────────────────────────────

def _render_view_descubrir() -> None:
    """
    Renderiza la vista Descubrir: input de captura y historial de conversación.

    Solo contiene el formulario de captura/pregunta y el historial.
    Los botones de repaso y quiz viven en la vista Dominar.
    El formulario limpia el input tras el submit.  Cada entrada del historial
    muestra un badge de modo y, si es captura, la tarjeta de concepto completa.
    """
    st.markdown("### Descubrir")
    st.markdown(
        "<p style='color:#7f849c; font-size:0.85rem; margin-top:-0.5rem;'>"
        "Escribe un término para aprenderlo, o hazle una pregunta a Nura.</p>",
        unsafe_allow_html=True,
    )

    # ── Sprint 24: streak y progreso de meta diaria ────────────────────────────
    _uid_desc = _current_user_id()
    render_streak(
        streak=get_streak(_uid_desc),
        today=get_today_count(_uid_desc),
        goal=get_daily_goal(_uid_desc),
    )

    with st.form(key="chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_input = st.text_input(
                label="input",
                label_visibility="collapsed",
                placeholder="Ej: tasa de interés · ¿qué es la amortización?",
            )
        with col_btn:
            submitted = st.form_submit_button("Enviar", use_container_width=True, type="primary")

    if submitted and user_input.strip():
        with st.status("🔍 Analizando...", expanded=True) as _status:
            _status.write("🧠 Procesando con IA...")
            _status.write("🔗 Buscando conexiones...")
            try:
                _handle_submit(user_input.strip())
                _status.update(label="✓ Listo", state="complete", expanded=False)
                # Sprint 24: toast si se acaba de completar la meta diaria
                _uid_after = _current_user_id()
                if get_today_count(_uid_after) >= get_daily_goal(_uid_after):
                    st.toast("¡Meta del día cumplida! 🔥")
            except Exception as exc:
                _status.update(label="Error al procesar", state="error")
                st.error(f"Error al procesar: {exc}")

    # Historial de conversacion
    if st.session_state.history:
        st.markdown("---")
        st.markdown(
            "<p style='color:#6c7086; font-size:0.8rem; margin-bottom:1rem;'>"
            f"Historial de sesión — {len(st.session_state.history)} entrada(s)</p>",
            unsafe_allow_html=True,
        )

        for hist_idx, entry in enumerate(st.session_state.history):
            result = entry["result"]
            mode = result.get("mode", "")

            # Badge de modo con colores diferenciados
            _BADGES = {
                "capture":            ("#a6e3a1", "✓ Capturado"),
                "reclassify":         ("#cba6f7", "↻ Reclasificado"),
                "question":           ("#60a0ff", "Tutor"),
                "review":             ("#cba6f7", "Repaso"),
                "quiz":               ("#f9e2af", "Quiz"),
                "clarify":            ("#fab387", "Ambigüedad"),
                "spelling":           ("#f38ba8", "Ortografía"),
                "confirm_reclassify": ("#74c7ec", "¿Reclasificar?"),
            }
            badge_color, badge_label = _BADGES.get(mode, ("#6c7086", mode or "—"))
            badge = (
                f"<span style='background:{badge_color}22; color:{badge_color}; "
                f"border:1px solid {badge_color}44; border-radius:20px; "
                f"padding:3px 12px; font-size:0.75rem; font-weight:600;'>"
                f"{badge_label}</span>"
            )

            st.markdown(
                f"<div style='display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;'>"
                f"<p style='color:#a6adc8; font-size:0.95rem; margin:0;'>"
                f"<strong>{entry['input']}</strong></p>"
                f"{badge}</div>",
                unsafe_allow_html=True,
            )

            if mode in ("capture", "reclassify") and result.get("current_concept"):
                if mode == "reclassify":
                    st.markdown(
                        "<p style='color:#cba6f7; font-size:0.85rem; "
                        "margin-bottom:0.5rem;'>"
                        "Ya conocía este término — lo reclasifiqué con el nuevo contexto.</p>",
                        unsafe_allow_html=True,
                    )
                try:
                    render_concept_card(
                        result["current_concept"],
                        show_edit=True,
                        card_index=hist_idx,
                    )
                except Exception as _card_err:
                    st.warning(
                        f"No se pudo renderizar la tarjeta del concepto: {_card_err}"
                    )

                conns = result.get("new_connections") or []
                if conns:
                    st.markdown(
                        f"<p style='color:#7f849c; font-size:0.8rem; margin-top:0.25rem;'>"
                        f"Conectado con {len(conns)} concepto(s) previo(s).</p>",
                        unsafe_allow_html=True,
                    )

            # Sprint 14: término ambiguo → mostrar opciones para elegir significado
            elif mode == "clarify":
                options = result.get("clarification_options") or []
                original_term = entry["input"]
                st.markdown(
                    f"<div style='background:#fab38711; border:1px solid #fab38744; "
                    f"border-left:4px solid #fab387; border-radius:10px; "
                    f"padding:0.8rem 1rem; margin-bottom:0.5rem;'>"
                    f"<p style='color:#fab387; font-size:0.9rem; margin:0;'>"
                    f"<strong>'{_html.escape(original_term)}'</strong> puede significar varias cosas "
                    f"— ¿a cuál te refieres?</p></div>",
                    unsafe_allow_html=True,
                )
                for meaning_idx, meaning in enumerate(options):
                    if st.button(
                        meaning,
                        key=f"clarify_{original_term[:15]}_{hist_idx}_{meaning_idx}",
                        use_container_width=False,
                    ):
                        # Eliminar la entrada de clarificación antes de añadir
                        # la resuelta: evita que aparezca el término dos veces.
                        del st.session_state.history[hist_idx]
                        with st.spinner("Clasificando con el contexto elegido..."):
                            try:
                                _handle_submit(
                                    original_term,
                                    user_context=f"[CLARIFIED]: {meaning}",
                                )
                            except Exception as exc:
                                st.error(f"Error: {exc}")
                        st.rerun()
                # Opción alternativa: buscar en web para resolver la ambigüedad
                _wsv_svg = (
                    '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"'
                    ' viewBox="0 0 24 24" fill="none" stroke="currentColor"'
                    ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                    '<circle cx="12" cy="12" r="10"/>'
                    '<line x1="2" y1="12" x2="22" y2="12"/>'
                    '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10'
                    ' 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
                    "</svg>"
                )
                st.markdown(
                    f"<span style='color:#6c7086; font-size:0.8rem;'>"
                    f"o si no sabes cuál es, Nura puede buscar en la web</span>",
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Buscar en web",
                    key=f"websearch_{original_term[:15]}_{hist_idx}",
                    help="Buscar la definición actualizada en internet",
                ):
                    del st.session_state.history[hist_idx]
                    with st.spinner("Buscando en la web..."):
                        try:
                            _handle_submit(
                                original_term,
                                user_context=(
                                    f"[WEBSEARCH]: buscar definición actualizada "
                                    f"de {original_term}"
                                ),
                            )
                        except Exception as exc:
                            st.error(f"Error: {exc}")
                    st.rerun()

            # Sprint 14: posible error ortográfico → confirmar o rechazar sugerencia
            elif mode == "spelling":
                suggestion = result.get("spelling_suggestion", "")
                original_term = entry["input"]
                if suggestion:
                    st.markdown(
                        f"<div style='background:#f38ba811; border:1px solid #f38ba844; "
                        f"border-left:4px solid #f38ba8; border-radius:10px; "
                        f"padding:0.8rem 1rem; margin-bottom:0.5rem;'>"
                        f"<p style='color:#f38ba8; font-size:0.9rem; margin:0;'>"
                        f"¿Quisiste decir "
                        f"<strong>'{_html.escape(suggestion)}'</strong>?</p></div>",
                        unsafe_allow_html=True,
                    )
                    col_yes, col_no = st.columns([1, 1])
                    with col_yes:
                        if st.button(
                            f"Sí, usar '{suggestion}'",
                            key=f"spell_yes_{original_term[:15]}_{hist_idx}",
                            type="primary",
                        ):
                            del st.session_state.history[hist_idx]
                            with st.spinner("Capturando..."):
                                try:
                                    _handle_submit(
                                        suggestion,
                                        user_context="[CLARIFIED]: ",
                                    )
                                except Exception as exc:
                                    st.error(f"Error: {exc}")
                            st.rerun()
                    with col_no:
                        if st.button(
                            "No, capturar como está",
                            key=f"spell_no_{original_term[:15]}_{hist_idx}",
                        ):
                            del st.session_state.history[hist_idx]
                            with st.spinner("Capturando..."):
                                try:
                                    _handle_submit(
                                        original_term,
                                        user_context="[CLARIFIED]: ",
                                    )
                                except Exception as exc:
                                    st.error(f"Error: {exc}")
                            st.rerun()

            # Sprint 20: término ya clasificado — preguntar al usuario si es el mismo
            # o uno diferente antes de reclasificar.
            elif mode == "confirm_reclassify":
                original_term = entry["input"]
                existing_concept = result.get("current_concept")
                st.markdown(
                    f"<div style='background:#74c7ec11; border:1px solid #74c7ec44; "
                    f"border-left:4px solid #74c7ec; border-radius:10px; "
                    f"padding:0.8rem 1rem; margin-bottom:0.5rem;'>"
                    f"<p style='color:#74c7ec; font-size:0.9rem; margin:0 0 0.4rem 0;'>"
                    f"Ya tengo <strong>'{_html.escape(original_term)}'</strong> en tu mapa. "
                    f"¿Es el mismo concepto o uno diferente?</p>"
                    f"<p style='color:#6c7086; font-size:0.8rem; margin:0;'>"
                    f"{'Categoría actual: ' + _html.escape(existing_concept.category) if existing_concept and existing_concept.category else ''}"
                    f"</p></div>",
                    unsafe_allow_html=True,
                )
                col_same, col_diff = st.columns(2)
                with col_same:
                    if st.button(
                        "Sí, actualizar contexto",
                        key=f"cr_same_{original_term[:15]}_{hist_idx}",
                        type="primary",
                        use_container_width=True,
                        help="Reclasifica el concepto con el nuevo contexto que proporcionaste",
                    ):
                        del st.session_state.history[hist_idx]
                        with st.spinner("Reclasificando..."):
                            try:
                                _handle_submit(
                                    original_term,
                                    user_context="[CLARIFIED]: reclasificar con contexto actualizado",
                                )
                            except Exception as exc:
                                st.error(f"Error: {exc}")
                        st.rerun()
                with col_diff:
                    if st.button(
                        "No, es diferente — buscar en web",
                        key=f"cr_diff_{original_term[:15]}_{hist_idx}",
                        use_container_width=True,
                        help="Busca en la web para distinguir este concepto del que ya tienes",
                    ):
                        del st.session_state.history[hist_idx]
                        with st.spinner("Buscando en la web..."):
                            try:
                                _handle_submit(
                                    original_term,
                                    user_context=(
                                        f"[WEBSEARCH]: buscar definición actualizada "
                                        f"de {original_term}"
                                    ),
                                )
                            except Exception as exc:
                                st.error(f"Error: {exc}")
                        st.rerun()

            elif mode == "quiz" and result.get("quiz_questions"):
                # Mostrar respuesta de quiz primero, luego el quiz interactivo
                response_text = _extract_text(result.get("response", ""))
                if response_text:
                    st.markdown(
                        f"<p style='color:#f9e2af; font-size:0.88rem; margin-bottom:0.75rem;'>"
                        f"{_html.escape(response_text)}</p>",
                        unsafe_allow_html=True,
                    )
                quiz_results = render_quiz(result["quiz_questions"], quiz_index=hist_idx)
                # Sprint 12: intervención post-quiz cuando el score es bajo (< 60%)
                if quiz_results:
                    _total_q = len(quiz_results)
                    _correct_q = sum(1 for v in quiz_results.values() if v)
                    _pct_q = int(_correct_q / _total_q * 100) if _total_q else 0
                    if _pct_q < 60:
                        st.markdown(
                            "<div style='background:#f38ba811; border:1px solid #f38ba844; "
                            "border-left:4px solid #f38ba8; border-radius:10px; "
                            "padding:0.8rem 1rem; margin-top:0.75rem;'>"
                            "<p style='color:#f38ba8; font-size:0.88rem; margin:0 0 0.5rem 0;'>"
                            "Noto que esta área te está costando — "
                            "¿quieres que el tutor te explique estos conceptos de forma diferente?</p>"
                            "</div>",
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "Sí, explícame",
                            key=f"quiz_help_{entry.get('input', '')[:20]}",
                            type="primary",
                        ):
                            _handle_submit(
                                "Explícame de forma diferente los conceptos que más me están costando"
                            )
                            st.rerun()
                    # Banner motivador tras guardar resultados del quiz (Sprint 16)
                    try:
                        from agents.motivator_agent import get_motivational_message
                        _mot_msg = get_motivational_message(
                            user_id=_current_user_id(),
                            quiz_score=float(_pct_q),
                        )
                        render_motivational_toast(_mot_msg)
                    except Exception:
                        pass
            else:
                # Respuesta del tutor o del agente de repaso — texto enriquecido
                response_text = _extract_text(result.get("response", ""))
                sources = result.get("sources") or []

                # Badge "🌐 Web search" cuando el tutor uso fuentes externas
                if mode == "question" and sources:
                    st.markdown(
                        "<span style='background:#60a0ff22; color:#60a0ff; "
                        "border:1px solid #60a0ff44; border-radius:20px; "
                        "padding:2px 10px; font-size:0.72rem; font-weight:600;'>"
                        "Consultando fuentes actualizadas</span>",
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f"<div style='color:#cdd6f4; font-size:0.9rem; padding:1rem 1.25rem; "
                    f"background:#313244; border-radius:12px; border:1px solid #45475a; "
                    f"line-height:1.7;'>{_html.escape(response_text)}</div>",
                    unsafe_allow_html=True,
                )

                # Fuentes web debajo de la respuesta (solo en modo question)
                if mode == "question" and sources:
                    render_sources(sources)

                # Diagrama SVG automático (Sprint 17) — solo en modo question
                if mode == "question":
                    _svg = result.get("diagram_svg") or ""
                    if _svg:
                        render_diagram(_svg)

                # ── Sprint 18: sugerencias de conceptos nuevos ────────────
                # Muestra un banner sutil con checkboxes para que el usuario
                # pueda agregar con un click los términos detectados en la
                # respuesta del tutor.  Se omite si la lista está vacía o
                # si ya se procesó esta entrada del historial.
                if mode == "question":
                    _sc_key   = f"_sc_done_{hist_idx}"
                    _suggested = result.get("suggested_concepts") or []
                    if _suggested and not st.session_state.get(_sc_key):
                        st.markdown(
                            "<div style='margin-top:0.75rem; padding:0.8rem 1rem; "
                            "background:#1e1e2e; border:1px solid #45475a; "
                            "border-radius:10px; font-size:0.82rem; color:#a6adc8;'>"
                            "<strong style='color:#cdd6f4;'>Encontré estos conceptos "
                            "en mi respuesta — ¿quieres agregarlos a tu mapa?</strong>",
                            unsafe_allow_html=True,
                        )
                        _sc_checked_key = f"_sc_checks_{hist_idx}"
                        if _sc_checked_key not in st.session_state:
                            st.session_state[_sc_checked_key] = {}
                        for _sc_term in _suggested:
                            _cb_key = f"_sc_cb_{hist_idx}_{_sc_term[:20]}"
                            st.session_state[_sc_checked_key][_sc_term] = st.checkbox(
                                _sc_term,
                                value=st.session_state[_sc_checked_key].get(_sc_term, False),
                                key=_cb_key,
                            )
                        if st.button(
                            "Agregar seleccionados",
                            key=f"_sc_btn_{hist_idx}",
                        ):
                            _to_add = [
                                t for t, v in st.session_state[_sc_checked_key].items() if v
                            ]
                            for _sc_term in _to_add:
                                _handle_submit(
                                    _sc_term,
                                    user_context="[CLARIFIED]: concepto técnico detectado en respuesta del tutor",
                                )
                            st.session_state[_sc_key] = True
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div style="text-align:center; padding:3rem 1rem; color:#45475a;">
                <div style="margin-bottom:0.75rem; color:#45475a;">
                  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24"
                       fill="none" stroke="currentColor" stroke-width="1.2"
                       stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
                    <path d="M20 3v4m2-2h-4M4 17v2m1-1H3"/>
                  </svg>
                </div>
                <p style="font-size:1rem; color:#6c7086;">
                    Tu historial aparecerá aquí.<br>
                    Escribe un término para aprenderlo, una pregunta para el tutor,
                    o pulsa <strong>Repasar</strong>.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── Flashcard session helpers ─────────────────────────────────────────────────

def _fc_start_session(fc_concepts: list) -> None:
    """
    Inicializa una nueva sesión de flashcards en st.session_state.

    Carga la cola con todos los conceptos clasificados que tienen flashcard,
    registra el nivel de dominio inicial de cada uno para poder calcular
    cuáles subieron al final de la sesión, y resetea todos los contadores.

    Parámetros
    ----------
    fc_concepts : Lista de Concept con flashcard_front no vacío y is_classified=True.
    """
    st.session_state.fc_queue = [c.id for c in fc_concepts]
    st.session_state.fc_show_back = False
    st.session_state.fc_session_done = False
    st.session_state.fc_results = {
        c.id: {
            "correct":     0,
            "incorrect":   0,
            "level_before": c.mastery_level,
            "level_after":  c.mastery_level,
        }
        for c in fc_concepts
    }


def _render_session_summary() -> None:
    """
    Muestra el resumen al completar una sesión de flashcards.

    Calcula y presenta el total de aciertos, errores y qué conceptos
    subieron de nivel de dominio durante la sesión.  Ofrece un botón
    para iniciar una nueva sesión.
    """
    results = st.session_state.fc_results
    total_correct   = sum(r["correct"]   for r in results.values())
    total_incorrect = sum(r["incorrect"] for r in results.values())
    leveled_up = [
        cid for cid, r in results.items()
        if r["level_after"] > r["level_before"]
    ]

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #313244 0%, #1e1e2e 100%);
            border: 1px solid #a6e3a144;
            border-left: 4px solid #a6e3a1;
            border-radius: 12px;
            padding: 1.5rem 2rem;
            text-align: center;
            margin-bottom: 1rem;
        ">
            <div style="margin:0 0 0.5rem 0; color:#a6e3a1;">
              <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24"
                   fill="none" stroke="currentColor" stroke-width="1.5"
                   stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <path d="m9 11 3 3L22 4"/>
              </svg>
            </div>
            <h3 style="color:#a6e3a1; margin:0 0 1rem 0; font-size:1.3rem;">
                Sesión completada
            </h3>
            <div style="display:flex; justify-content:center; gap:2rem; flex-wrap:wrap;">
                <div>
                    <p style="color:#a6e3a1; font-size:1.8rem; font-weight:700; margin:0;">
                        {total_correct}
                    </p>
                    <p style="color:#6c7086; font-size:0.8rem; margin:0;">aciertos</p>
                </div>
                <div>
                    <p style="color:#f38ba8; font-size:1.8rem; font-weight:700; margin:0;">
                        {total_incorrect}
                    </p>
                    <p style="color:#6c7086; font-size:0.8rem; margin:0;">errores</p>
                </div>
                <div>
                    <p style="color:#f9e2af; font-size:1.8rem; font-weight:700; margin:0;">
                        {len(leveled_up)}
                    </p>
                    <p style="color:#6c7086; font-size:0.8rem; margin:0;">subieron de nivel</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if leveled_up:
        st.markdown(
            "<p style='color:#f9e2af; font-size:0.85rem; margin-bottom:0.25rem;'>"
            "⭐ Conceptos que subieron de nivel:</p>",
            unsafe_allow_html=True,
        )
        for cid in leveled_up:
            r = results[cid]
            try:
                c = get_concept_by_id(cid)
                stars_before = "★" * r["level_before"] + "☆" * (5 - r["level_before"])
                stars_after  = "★" * r["level_after"]  + "☆" * (5 - r["level_after"])
                st.markdown(
                    f"<p style='color:#cdd6f4; font-size:0.85rem; margin:0.1rem 0;'>"
                    f"&nbsp;&nbsp;<strong>{c.term}</strong>: "
                    f"<span style='color:#6c7086;'>{stars_before}</span> → "
                    f"<span style='color:#f9e2af;'>{stars_after}</span></p>",
                    unsafe_allow_html=True,
                )
            except Exception:
                pass

    if st.button("Nueva sesión", use_container_width=False):
        st.session_state.fc_queue = []
        st.session_state.fc_session_done = False
        st.rerun()

    # Banner motivador al terminar la sesión de flashcards (Sprint 16)
    try:
        from agents.motivator_agent import get_motivational_message
        _mot_msg = get_motivational_message(user_id=_current_user_id())
        render_motivational_toast(_mot_msg)
    except Exception:
        pass  # nunca bloquear el flujo principal por el toast


def _render_flashcard_session(concepts: list) -> None:
    """
    Renderiza la sesión completa de flashcards con lógica de cola inteligente.

    Flujo de la sesión
    ------------------
    1. Si no hay sesión activa: botón 'Iniciar sesión' carga la cola.
    2. Se muestra la flashcard actual (frente por defecto).
    3. El botón 'Voltear' revela el reverso.
    4. Con el reverso visible aparecen '✅ Lo sabía' y '❌ No lo sabía':
         ✅ → record_flashcard_result(True), la tarjeta sale de la cola.
         ❌ → record_flashcard_result(False), la tarjeta va al final de la cola.
    5. Al vaciar la cola se muestra el resumen de sesión.

    La tarjeta sale de la cola tras el primer acierto (no requiere repetición
    adicional salvo que la especificación lo indique).

    Parámetros
    ----------
    concepts : Lista completa de Concept cargada desde la BD.
    """
    fc_concepts = [c for c in concepts if c.flashcard_front and c.is_classified]

    if not fc_concepts:
        st.info("Aún no hay flashcards. Captura algunos términos para generarlas.")
        return

    # ── Sin sesión activa ─────────────────────────────────────────────────────
    if not st.session_state.fc_queue and not st.session_state.fc_session_done:
        st.markdown(
            f"<p style='color:#7f849c; font-size:0.85rem;'>"
            f"{len(fc_concepts)} tarjeta(s) disponibles. "
            f"Pulsa el botón para empezar.</p>",
            unsafe_allow_html=True,
        )
        if st.button("Iniciar flashcards", use_container_width=False, type="primary"):
            _fc_start_session(fc_concepts)
            st.rerun()
        return

    # ── Sesión completada ─────────────────────────────────────────────────────
    if st.session_state.fc_session_done or not st.session_state.fc_queue:
        _render_session_summary()
        return

    # ── Tarjeta en curso ──────────────────────────────────────────────────────
    concept_map = {c.id: c for c in fc_concepts}
    # Saltear IDs huérfanos (concepto eliminado entre reruns)
    while st.session_state.fc_queue and st.session_state.fc_queue[0] not in concept_map:
        st.session_state.fc_queue.pop(0)
    if not st.session_state.fc_queue:
        st.session_state.fc_session_done = True
        st.rerun()
        return

    current_id = st.session_state.fc_queue[0]
    current = concept_map[current_id]

    # Progreso de la sesión
    done_count = sum(
        1 for cid, r in st.session_state.fc_results.items()
        if r["correct"] > 0
    )
    total_count = len(st.session_state.fc_results)
    st.markdown(
        f"<p style='color:#6c7086; font-size:0.8rem; margin-bottom:0.75rem;'>"
        f"En cola: {len(st.session_state.fc_queue)} — "
        f"Completadas: {done_count}/{total_count}</p>",
        unsafe_allow_html=True,
    )

    # Renderiza la flashcard (con indicador de racha desde components.py)
    fc_html = render_flashcard(current, show_back=st.session_state.fc_show_back)
    st.markdown(fc_html, unsafe_allow_html=True)

    # Botones según el estado de la tarjeta
    if not st.session_state.fc_show_back:
        col_flip, col_term, col_spacer = st.columns([1, 1, 2])
        with col_flip:
            if st.button("Voltear", use_container_width=True):
                st.session_state.fc_show_back = True
                st.rerun()
        with col_term:
            if st.button("Terminar sesión", use_container_width=True):
                st.session_state.fc_session_done = True
                st.rerun()
    else:
        col_yes, col_no, col_term2, col_spacer = st.columns([1, 1, 1, 1])
        with col_yes:
            if st.button("Lo sabía", use_container_width=True, type="primary"):
                _uid = _current_user_id()
                updated = record_flashcard_result(current_id, correct=True, user_id=_uid)
                st.session_state.fc_results[current_id]["correct"] += 1
                st.session_state.fc_results[current_id]["level_after"] = updated.mastery_level
                # La tarjeta sale de la cola tras el primer acierto
                st.session_state.fc_queue.pop(0)
                st.session_state.fc_show_back = False
                # Actualiza métrica diaria
                s = get_or_create_daily_summary(date.today(), user_id=_uid)
                update_daily_summary(
                    date.today(),
                    user_id=_uid,
                    concepts_reviewed=s.concepts_reviewed + 1,
                )
                if not st.session_state.fc_queue:
                    st.session_state.fc_session_done = True
                st.rerun()
        with col_no:
            if st.button("No lo sabía", use_container_width=True):
                record_flashcard_result(current_id, correct=False, user_id=_current_user_id())
                st.session_state.fc_results[current_id]["incorrect"] += 1
                st.session_state.fc_queue.pop(0)
                # Sprint 20: si el concepto ya tuvo 3+ errores en esta sesión,
                # sacarlo de la cola y marcarlo como diferido para mañana.
                # Esto evita el loop infinito de una flashcard que no se sabe.
                _incorrect_count = st.session_state.fc_results[current_id]["incorrect"]
                if _incorrect_count < 3:
                    # Reprogramar al final de la cola
                    st.session_state.fc_queue.append(current_id)
                else:
                    # Deferred: no vuelve en esta sesión
                    st.session_state.fc_results[current_id]["deferred"] = True
                st.session_state.fc_show_back = False
                st.rerun()
        with col_term2:
            if st.button("Terminar sesión", use_container_width=True):
                st.session_state.fc_session_done = True
                st.rerun()


# ── Perfil de aprendizaje ─────────────────────────────────────────────────────

def _render_learning_profile() -> None:
    """
    Renderiza la seccion 'Mi perfil de aprendizaje' en Tab 2.

    Muestra cinco elementos del perfil adaptativo del usuario:
    1. Insight semanal con métricas de la última semana (Sprint 12).
    2. Grafico de barras horizontal con % de dominio promedio por categoria.
    3. Badges de fortaleza y area de refuerzo calculados a partir del grafico.
    4. Metrica de racha de dias activos consecutivos.
    5. Metrica de conceptos dominados (mastery >= 4).

    No llama a ningun modelo externo — todos los datos provienen de la BD.
    """
    st.markdown("### Perfil de dominio")

    uid = _current_user_id()
    mastery_by_cat = get_mastery_by_category(user_id=uid)
    streak = get_streak(user_id=uid)
    dominated = get_dominated_concepts(user_id=uid)

    # ── Sprint 12: insight semanal ─────────────────────────────────────────────
    weekly = get_weekly_insight_data(user_id=uid)
    st.markdown(
        "<p style='color:#60a0ff; font-size:0.8rem; font-weight:700; "
        "letter-spacing:0.08em; text-transform:uppercase; margin:0 0 0.6rem 0;'>"
        "Insight semanal</p>",
        unsafe_allow_html=True,
    )
    col_w1, col_w2, col_w3, col_w4 = st.columns(4)
    with col_w1:
        st.metric(
            "Esta semana",
            weekly["conceptos_esta_semana"],
            help="Conceptos capturados en los últimos 7 días",
        )
    with col_w2:
        st.metric(
            "Racha activa",
            f"{weekly['racha']} día(s)",
            help="Días consecutivos con actividad",
        )
    with col_w3:
        st.metric(
            "Dominados",
            weekly["conceptos_dominados"],
            help="Conceptos con mastery >= 4",
        )
    with col_w4:
        pref = "Flashcards" if weekly.get("learning_pref") == "flashcards" else "Conversación"
        st.metric("Estilo preferido", pref, help="Basado en tus revisiones")

    if weekly["categoria_mas_debil"]:
        st.markdown(
            f"<div style='background:#f38ba811; border:1px solid #f38ba833; "
            f"border-radius:8px; padding:0.5rem 1rem; margin:0.5rem 0 1rem 0; "
            f"font-size:0.84rem; color:#f38ba8;'>"
            f"Área a reforzar esta semana: <strong>{weekly['categoria_mas_debil']}</strong>"
            f"</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── Metricas clave ────────────────────────────────────────────────────────
    col_streak, col_dom, col_spacer = st.columns([1, 1, 2])
    with col_streak:
        st.metric(
            label="Racha activa",
            value=f"{streak} dia(s)",
            help="Dias consecutivos con al menos una captura o revision",
        )
    with col_dom:
        st.metric(
            label="Conceptos dominados",
            value=len(dominated),
            help="Conceptos con nivel de dominio >= 4",
        )

    # ── Grafico de dominio por categoria ──────────────────────────────────────
    if not mastery_by_cat:
        st.info("Captura y clasifica algunos conceptos para ver tu perfil de aprendizaje.")
        return

    # Convierte a % sobre 5 para que el grafico vaya de 0 a 100
    pct_by_cat = {cat: round(avg / 5.0 * 100, 1) for cat, avg in mastery_by_cat.items()}

    st.markdown(
        "<p style='color:#a6adc8; font-size:0.85rem; margin-top:0.75rem;'>"
        "Dominio promedio por categoria (%):</p>",
        unsafe_allow_html=True,
    )
    st.bar_chart(pct_by_cat, color="#60a0ff")

    # ── Badges de fortaleza y refuerzo ────────────────────────────────────────
    if len(mastery_by_cat) >= 1:
        strongest_cat = max(mastery_by_cat, key=mastery_by_cat.__getitem__)
        weakest_cat = min(mastery_by_cat, key=mastery_by_cat.__getitem__)

        col_strong, col_weak = st.columns(2)
        with col_strong:
            st.markdown(
                f"<div style='background:#a6e3a122; border:1px solid #a6e3a144; "
                f"border-radius:8px; padding:0.6rem 1rem;'>"
                f"<span style='font-size:0.8rem; color:#a6e3a1; font-weight:700;'>"
                f"Mas fuerte en:</span><br>"
                f"<span style='color:#cdd6f4; font-weight:600;'>{strongest_cat}</span>"
                f"<span style='color:#a6adc8; font-size:0.8rem;'>"
                f" ({pct_by_cat[strongest_cat]:.0f}%)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with col_weak:
            st.markdown(
                f"<div style='background:#f38ba822; border:1px solid #f38ba844; "
                f"border-radius:8px; padding:0.6rem 1rem;'>"
                f"<span style='font-size:0.8rem; color:#f38ba8; font-weight:700;'>"
                f"Necesita refuerzo:</span><br>"
                f"<span style='color:#cdd6f4; font-weight:600;'>{weakest_cat}</span>"
                f"<span style='color:#a6adc8; font-size:0.8rem;'>"
                f" ({pct_by_cat[weakest_cat]:.0f}%)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ── Vista: Dominar ────────────────────────────────────────────────────────────

def _render_view_dominar() -> None:
    """
    Renderiza la vista Dominar: tarjetas de acción, resumen diario,
    flashcards (solo si hay sesión activa), mis conceptos y perfil.

    Sprint 21 — nuevo layout:
      1. Header con título y subtítulo.
      2. Dos cards de acción: Repasar hoy / Quiz rápido.
      3. Separador.
      4. Resumen del día (3 métricas).
      5. Separador.
      6. Flashcards (solo si hay sesión activa o pendientes).
      7. Separador.
      8. Mis conceptos — categorías colapsadas por defecto con expander.
      9. Separador.
      10. Perfil de dominio.

    Carga datos frescos desde la BD en cada rerun para reflejar conceptos
    recién capturados en la vista Descubrir.
    """
    uid = _current_user_id()
    concepts = get_all_concepts(user_id=uid)
    due_today_raw = get_concepts_due_today(user_id=uid)
    # Sprint 20: filtrar due_today a solo los que tienen flashcard.
    due_today = [
        c for c in due_today_raw
        if c.flashcard_front and getattr(c, "is_classified", False)
    ]
    classified_with_fc = [
        c for c in concepts
        if getattr(c, "is_classified", False) and c.flashcard_front
    ]
    n_due = len(due_today)
    n_fc = len(classified_with_fc)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("### Dominar")
    st.markdown(
        "<p style='color:#7f849c; font-size:0.85rem; margin-top:-0.5rem;'>"
        "Repasa, practica y consolida lo que has aprendido.</p>",
        unsafe_allow_html=True,
    )

    # ── Sección de acción rápida: dos cards grandes ───────────────────────────
    _SVG_REFRESH = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24"'
        ' fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
        '<path d="M8 16H3v5"/>'
        '</svg>'
    )
    _SVG_BRAIN = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24"'
        ' fill="none" stroke="currentColor" stroke-width="2"'
        ' stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.88A2.5 2.5 0 0 1 9.5 2Z"/>'
        '<path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.88A2.5 2.5 0 0 0 14.5 2Z"/>'
        '</svg>'
    )

    col_rep, col_quiz = st.columns(2)
    with col_rep:
        _rep_accent = "#60a0ff" if n_due > 0 else "#45475a"
        st.markdown(
            f"""<div style="background:#1e283a; border:1px solid {_rep_accent}44;
                border-left:4px solid {_rep_accent}; border-radius:12px;
                padding:1rem 1.25rem; margin-bottom:0.5rem;">
                <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.35rem;">
                    <span style="color:{_rep_accent}; opacity:0.9;">{_SVG_REFRESH}</span>
                    <span style="color:{_rep_accent}; font-weight:700; font-size:1rem;">
                        Repasar hoy</span>
                </div>
                <p style="color:#6c7086; font-size:0.82rem; margin:0;">
                    {"<strong style='color:#cba6f7;'>" + str(n_due) + " concepto(s)</strong> te esperan hoy."
                     if n_due > 0 else "Estás al día — no hay pendientes."}
                </p>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button(
            f"Repasar ahora ({n_due})" if n_due > 0 else "Repasar ahora",
            use_container_width=True,
            type="primary" if n_due > 0 else "secondary",
            disabled=(n_due == 0),
            key="btn_repasar_top",
        ):
            _fc_start_session(due_today)
            st.rerun()

    with col_quiz:
        st.markdown(
            f"""<div style="background:#1f1b2e; border:1px solid #cba6f744;
                border-left:4px solid #cba6f7; border-radius:12px;
                padding:1rem 1.25rem; margin-bottom:0.5rem;">
                <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.35rem;">
                    <span style="color:#cba6f7; opacity:0.9;">{_SVG_BRAIN}</span>
                    <span style="color:#cba6f7; font-weight:700; font-size:1rem;">
                        Quiz rápido</span>
                </div>
                <p style="color:#6c7086; font-size:0.82rem; margin:0;">
                    Pon a prueba tu conocimiento con preguntas de opción múltiple.
                </p>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button(
            "Iniciar quiz",
            use_container_width=True,
            key="btn_quiz_dominar",
        ):
            with st.spinner("Generando quiz con Gemini..."):
                try:
                    _handle_submit("ponme a prueba")
                except Exception as exc:
                    st.error(f"Error al generar el quiz: {exc}")
            st.session_state.current_view = "descubrir"
            st.rerun()

    st.markdown("---")

    # ── Resumen del día ───────────────────────────────────────────────────────
    st.markdown(
        "<p style='color:#60a0ff; font-size:0.8rem; font-weight:700; "
        "letter-spacing:0.08em; text-transform:uppercase; margin:0 0 0.6rem 0;'>"
        "Resumen de hoy</p>",
        unsafe_allow_html=True,
    )
    today = date.today()
    summary = get_or_create_daily_summary(today, user_id=uid)
    render_daily_summary(summary)

    st.markdown("---")

    # ── Flashcards (solo si hay sesión activa o hay cola pendiente) ───────────
    _fc_active = bool(st.session_state.fc_queue) or st.session_state.fc_session_done
    if _fc_active or n_fc > 0:
        st.markdown(
            "<p style='color:#60a0ff; font-size:0.8rem; font-weight:700; "
            "letter-spacing:0.08em; text-transform:uppercase; margin:0 0 0.6rem 0;'>"
            "Flashcards</p>",
            unsafe_allow_html=True,
        )
        if not st.session_state.fc_queue and not st.session_state.fc_session_done and n_fc > 0:
            fc_label = f"Iniciar todas las flashcards ({n_fc})"
            if st.button(fc_label, use_container_width=False, key="btn_fc_all"):
                _fc_start_session(classified_with_fc)
                st.rerun()
        _render_flashcard_session(concepts)
        st.markdown("---")

    # ── Mis conceptos — categorías colapsadas por defecto ─────────────────────
    st.markdown(
        "<p style='color:#60a0ff; font-size:0.8rem; font-weight:700; "
        "letter-spacing:0.08em; text-transform:uppercase; margin:0 0 0.6rem 0;'>"
        "Mis conceptos</p>",
        unsafe_allow_html=True,
    )

    # Alerta de conceptos pendientes con opción de reintento
    unclassified = get_unclassified_concepts(user_id=uid)
    if unclassified:
        st.markdown(
            f"<div style='background:#f38ba822; border:1px solid #f38ba855; "
            f"border-radius:10px; padding:0.75rem 1rem; margin-bottom:1rem;'>"
            f"<span style='color:#f38ba8; font-weight:700;'>{len(unclassified)} concepto(s) pendiente(s)</span>"
            f"<span style='color:#a6adc8; font-size:0.85rem;'> — la clasificación no se completó todavía.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        for uc in unclassified:
            col_label, col_retry, col_del = st.columns([4, 1, 1])
            with col_label:
                st.markdown(
                    f"<p style='color:#cdd6f4; margin:0; padding:0.4rem 0;'>"
                    f"<strong>{_html.escape(uc.term)}</strong>"
                    f"<span style='color:#6c7086; font-size:0.8rem; margin-left:0.5rem;'>"
                    f"(capturado {uc.created_at.strftime('%d/%m/%Y')})</span></p>",
                    unsafe_allow_html=True,
                )
            with col_retry:
                if st.button("Reintentar", key=f"retry_{uc.id}", use_container_width=True):
                    with st.spinner(f"Reclasificando '{uc.term}'..."):
                        try:
                            _handle_submit(uc.term, user_context=uc.user_context)
                        except Exception as exc:
                            st.error(f"Error: {exc}")
                    st.rerun()
            with col_del:
                _confirm_key = f"_del_confirm_{uc.id}"
                if not st.session_state.get(_confirm_key, False):
                    if st.button("Eliminar", key=f"del_{uc.id}", use_container_width=True):
                        st.session_state[_confirm_key] = True
                        st.rerun()
                else:
                    st.warning(f"¿Eliminar «{uc.term}»?")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("Sí", key=f"del_yes_{uc.id}", use_container_width=True, type="primary"):
                            delete_concept(uc.id, user_id=uid)
                            st.session_state.pop(_confirm_key, None)
                            st.rerun()
                    with col_no:
                        if st.button("No", key=f"del_no_{uc.id}", use_container_width=True):
                            st.session_state.pop(_confirm_key, None)
                            st.rerun()
        st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

    if not concepts:
        st.info("Todavía no tienes conceptos. Ve a Descubrir para agregar el primero.")
    else:
        from collections import defaultdict
        by_category: dict[str, list] = defaultdict(list)
        for c in concepts:
            by_category[c.category or "Sin categoría"].append(c)

        for cat, cat_concepts in sorted(by_category.items()):
            from ui.components import _category_color, render_concept_card
            color = _category_color(cat)
            # Sprint 21: cada categoría en un expander colapsado por defecto
            with st.expander(
                f"{cat.upper()} — {len(cat_concepts)} concepto(s)",
                expanded=False,
            ):
                for _ci, c in enumerate(cat_concepts):
                    try:
                        render_concept_card(
                            c,
                            show_edit=False,
                            show_actions=True,
                            card_index=_ci,
                        )
                    except Exception as _card_err:
                        st.warning(
                            f"No se pudo renderizar la tarjeta de '{c.term}': {_card_err}"
                        )

    st.markdown("---")

    # ── Perfil de dominio ─────────────────────────────────────────────────────
    _render_learning_profile()


# ── Vista: Conectar ───────────────────────────────────────────────────────────

def _render_view_conectar() -> None:
    """
    Renderiza la vista Conectar: mapa interactivo de conocimiento con filtros
    y panel de detalle de nodo.  Los datos se cargan frescos en cada rerun.
    """
    uid = _current_user_id()
    concepts   = get_all_concepts(user_id=uid)
    connections = get_all_connections(user_id=uid)

    st.markdown("### Conectar")

    if not concepts:
        st.info("El mapa aparecerá cuando tengas al menos un concepto capturado.")
        return

    # ── Selectbox de filtro rápido — encima del mapa ─────────────────────────
    # El click en nodo (pyvis JS) navega a ?nura_node=<id>&view=conectar.
    # _init_session() leyó ese param y lo guardó en map_filter_concept_id.
    # Aquí sincronizamos el selectbox con el valor de session_state.
    _concept_map = {c.term: c for c in concepts}
    _sel_opts    = ["— todos los nodos —"] + sorted(_concept_map.keys())

    # Si map_filter_concept_id fue establecido por un click en nodo (via URL param),
    # sincronizar map_selected_term con el nombre del concepto filtrado.
    _filter_id = st.session_state.get("map_filter_concept_id")
    if _filter_id and not st.session_state.get("map_selected_term"):
        _fc = next((c for c in concepts if c.id == _filter_id), None)
        if _fc:
            st.session_state.map_selected_term = _fc.term

    _current_sel = st.session_state.get("map_selected_term", _sel_opts[0])
    _sel_idx     = _sel_opts.index(_current_sel) if _current_sel in _sel_opts else 0

    _col_sel, _col_rst = st.columns([6, 1])
    with _col_sel:
        _chosen = st.selectbox(
            "Enfocar nodo",
            options=_sel_opts,
            index=_sel_idx,
            label_visibility="collapsed",
            help="Selecciona un concepto para ver solo sus conexiones directas",
            key="map_top_selector",
        )
    with _col_rst:
        _has_filter = st.session_state.get("map_filter_concept_id") is not None
        if st.button("✕", key="map_reset_btn", help="Ver todo el mapa", disabled=not _has_filter):
            st.session_state.map_filter_concept_id = None
            st.session_state.pop("map_selected_term", None)
            st.rerun()

    # Aplicar selección inmediatamente — sin botón adicional
    if _chosen and _chosen != _sel_opts[0]:
        _chosen_c = _concept_map.get(_chosen)
        if _chosen_c and st.session_state.get("map_filter_concept_id") != _chosen_c.id:
            st.session_state.map_filter_concept_id = _chosen_c.id
            st.session_state.map_selected_term     = _chosen
            st.rerun()
    elif _chosen == _sel_opts[0] and st.session_state.get("map_filter_concept_id") is not None:
        st.session_state.map_filter_concept_id = None
        st.session_state.pop("map_selected_term", None)
        st.rerun()

    # Calcula las categorías únicas para el multiselect
    all_categories = sorted({c.category for c in concepts if c.category})

    # ── Filtros ───────────────────────────────────────────────────────────────
    with st.expander("🔍  Filtros del mapa", expanded=False):
        col_cat, col_mastery = st.columns([3, 2])
        with col_cat:
            selected_cats = st.multiselect(
                "Categorías visibles",
                options=all_categories,
                default=[],
                placeholder="Todas las categorías",
                help="Selecciona una o varias categorías para filtrar los nodos.",
            )
        with col_mastery:
            min_mastery = st.slider(
                "Dominio mínimo",
                min_value=0,
                max_value=5,
                value=0,
                help="Muestra solo conceptos con nivel de dominio >= este valor.",
            )

    def _norm_cat(s: str) -> str:
        return (
            s.lower()
            .replace("é", "e").replace("ó", "o").replace("ú", "u")
            .replace("á", "a").replace("í", "i").strip()
        )

    visible_concepts = concepts
    if selected_cats:
        norm_sel = {_norm_cat(c) for c in selected_cats}
        visible_concepts = [c for c in concepts if _norm_cat(c.category) in norm_sel]
    if min_mastery > 0:
        visible_concepts = [c for c in visible_concepts if c.mastery_level >= min_mastery]

    visible_ids = {c.id for c in visible_concepts}
    visible_connections = [
        cn for cn in connections
        if cn.concept_id_a in visible_ids and cn.concept_id_b in visible_ids
    ]
    st.markdown(
        f"<p style='color:#7f849c; font-size:0.8rem; margin-bottom:0.5rem;'>"
        f"{len(visible_concepts)} nodo(s) — {len(visible_connections)} conexión(es). "
        f"Arrastra los nodos para reorganizar.</p>",
        unsafe_allow_html=True,
    )

    # Sprint 14: si hay un filtro de nodo activo, mostrar solo ese nodo y conexiones directas
    map_filter_id = st.session_state.get("map_filter_concept_id")
    focal_concept = next((c for c in concepts if c.id == map_filter_id), None) if map_filter_id else None

    if focal_concept:
        # Calcular nodos y conexiones del subgrafo del nodo seleccionado
        direct_conns = [
            cn for cn in connections
            if cn.concept_id_a == map_filter_id or cn.concept_id_b == map_filter_id
        ]
        neighbor_ids = {map_filter_id}
        for cn in direct_conns:
            neighbor_ids.add(cn.concept_id_a)
            neighbor_ids.add(cn.concept_id_b)
        focal_concepts = [c for c in concepts if c.id in neighbor_ids]

        col_info, col_btn = st.columns([3, 1])
        with col_info:
            st.markdown(
                f"<p style='color:#fab387; font-size:0.85rem; margin:0;'>"
                f"Mostrando: <strong>{_html.escape(focal_concept.term)}</strong> "
                f"y sus {len(direct_conns)} conexión(es) directas.</p>",
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("Ver todo el mapa", key="map_show_all"):
                st.session_state.map_filter_concept_id = None
                st.session_state.pop("map_selected_term", None)
                st.rerun()

        map_html = render_knowledge_map(focal_concepts, direct_conns)
    else:
        map_html = render_knowledge_map(
            concepts,
            connections,
            filter_categories=selected_cats if selected_cats else None,
            filter_min_mastery=min_mastery,
        )

    # El mapa (iframe pyvis) no puede llamar a Python; el JS pone nura_node en la
    # URL con replaceState y hace click en este botón para un rerun sin recarga
    # completa (evita perder session_state, p. ej. el usuario autenticado).
    st.button(
        "NURA_NODE_SYNC",
        key="nura_map_node_sync",
        help="NURA_MAP_INTERNAL_SYNC_V1",
        type="secondary",
    )

    st.components.v1.html(map_html, height=540, scrolling=False)

    # ── Panel de detalle del nodo enfocado ────────────────────────────────────
    if focal_concept:
        st.markdown("---")
        detail = get_concept_connections_detail(focal_concept.id, user_id=uid)
        render_concept_detail_panel(focal_concept, detail)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Punto de entrada de la aplicacion Streamlit.

    Configura la pagina, inyecta el CSS global, inicializa la BD y el estado
    de sesion, y renderiza los dos tabs principales de Nura.

    Debe llamarse desde el bloque if __name__ == '__main__' para que el archivo
    sea importable en los tests sin ejecutar el codigo de UI.
    """
    st.set_page_config(
        page_title="Nura — Aprendizaje Adaptativo",
        page_icon=_FAVICON,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(_CSS, unsafe_allow_html=True)

    init_db()

    # Aviso si init_db() no pudo conectar a PostgreSQL y cayó a SQLite.
    import db.schema as _db_schema
    if _db_schema.pg_fallback_active:
        _err_detail = _db_schema.pg_fallback_error
        _dbg = _db_schema.pg_debug_info
        st.warning(
            "⚠️ **No se pudo conectar a Supabase** — la app está usando SQLite local "
            "(los datos **no son persistentes** entre reinicios).  \n"
            f"**Error:** `{_err_detail}`  \n"
            f"**Diagnóstico:** `{_dbg}`  \n"
            "Verifica que `DATABASE_URL` esté correctamente configurada en los "
            "**Secrets de Streamlit Cloud** y que el proyecto Supabase no esté pausado.",
        )

    _init_session()

    # ── Verificación y refresh de sesión (Sprint 23) ───────────────────────────
    # Flujo al inicio de cada rerun:
    #   1. Si la sesión es válida (user_id presente y no expirada) → continuar.
    #      Además, si está próxima a expirar se renueva silenciosamente.
    #   2. Si hay user_id pero la sesión expiró → intentar refresh automático.
    #      Si el refresh falla (no hay session_expiry) → mostrar login.
    #   3. Sin sesión → mostrar login.
    _has_user_id = bool(st.session_state.get("user_id"))
    if _has_user_id:
        if is_session_valid():
            refresh_session()           # renovar si queda poco tiempo
        else:
            # Expiró: intentar refresh; si no hay expiry → limpiar sesión
            refreshed = refresh_session()
            if not refreshed:
                for _k in list(st.session_state.keys()):
                    del st.session_state[_k]

    # ── Autenticación (Sprint 11) ──────────────────────────────────────────────
    if st.session_state.get("user") is None:
        render_login_page()
        st.stop()

    # ── Onboarding (Sprint 15) ─────────────────────────────────────────────────
    # Si el usuario acaba de registrarse o tiene el perfil incompleto, mostrar
    # el flujo de onboarding antes de entrar a la app principal.
    from db.operations import needs_onboarding
    _current_user_obj = st.session_state["user"]
    if needs_onboarding(_current_user_obj):
        render_onboarding(_current_user_obj)
        st.stop()

    # ── Cargar perfil en session_state (Sprint 15) ─────────────────────────────
    # Se recarga en cada rerun para reflejar cambios guardados desde el sidebar.
    _current_user_obj = st.session_state["user"]
    st.session_state.user_profile = {
        "profession":    getattr(_current_user_obj, "profession",    ""),
        "learning_area": getattr(_current_user_obj, "learning_area", ""),
        "tech_level":    getattr(_current_user_obj, "tech_level",    ""),
    }

    # ── Sidebar (v0 design) ────────────────────────────────────────────────────
    current_user = st.session_state["user"]
    _uid_sidebar = _current_user_id()
    _streak_sidebar = get_streak(user_id=_uid_sidebar)

    # Build user avatar initials (up to 2 chars from username words)
    _words = current_user.username.split()
    _initials = (
        (_words[0][0] + _words[1][0]).upper()
        if len(_words) >= 2
        else current_user.username[:2].upper()
    )

    with st.sidebar:
        # ── Nura logo ─────────────────────────────────────────────────────────
        st.markdown(_NURA_LOGO_HTML, unsafe_allow_html=True)

        # ── User avatar card ──────────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:0.75rem;
                        padding:0.75rem;border-radius:12px;
                        background:#313244;margin-bottom:1.5rem;">
                <div style="width:40px;height:40px;border-radius:50%;
                            background:#60a0ff;display:flex;align-items:center;
                            justify-content:center;flex-shrink:0;">
                    <span style="font-size:0.85rem;font-weight:700;color:#1e1e2e;">
                        {_initials}
                    </span>
                </div>
                <div style="overflow:hidden;">
                    <p style="margin:0;font-size:0.9rem;font-weight:600;
                               color:#cdd6f4;white-space:nowrap;overflow:hidden;
                               text-overflow:ellipsis;">{current_user.username}</p>
                    <p style="margin:0;font-size:0.72rem;color:#60a0ff;
                               font-weight:500;">Nurian</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Navigation buttons ─────────────────────────────────────────────────
        st.markdown(
            """
            <p style="font-size:0.7rem;color:#6c7086;font-weight:600;
                      letter-spacing:0.1em;text-transform:uppercase;
                      margin:0 0 0.4rem 0;">Navegación</p>
            """,
            unsafe_allow_html=True,
        )

        _current_view = st.session_state.get("current_view", "descubrir")
        _due_sidebar = len(get_concepts_due_today(user_id=_uid_sidebar))

        # Lucide SVG icons — message-circle, book-open, network
        _SVG_MSG = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>'
            '</svg>'
        )
        _SVG_BOOK = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>'
            '<path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>'
            '</svg>'
        )
        _SVG_NET = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="16" y="16" width="6" height="6" rx="1"/>'
            '<rect x="2" y="16" width="6" height="6" rx="1"/>'
            '<rect x="9" y="2" width="6" height="6" rx="1"/>'
            '<path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/>'
            '<path d="M12 12V8"/>'
            '</svg>'
        )
        _SVG_LOGOUT = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
            '<polyline points="16 17 21 12 16 7"/>'
            '<line x1="21" y1="12" x2="9" y2="12"/>'
            '</svg>'
        )

        _dominar_label = (
            f"Dominar ({_due_sidebar})" if _due_sidebar > 0 else "Dominar"
        )
        _NAV_CONFIG = [
            ("descubrir", _SVG_MSG,  "Descubrir"),
            ("dominar",   _SVG_BOOK, _dominar_label),
            ("conectar",  _SVG_NET,  "Conectar"),
        ]

        for _view_id, _nav_svg, _nav_label in _NAV_CONFIG:
            _active    = _current_view == _view_id
            _icon_clr  = "#60a0ff" if _active else "#6c7086"
            _icon_bg   = "#60a0ff18" if _active else "transparent"
            _col_i, _col_b = st.columns([1, 5], gap="small")
            with _col_i:
                st.markdown(
                    f"<div style='width:30px;height:30px;border-radius:7px;"
                    f"background:{_icon_bg};display:flex;align-items:center;"
                    f"justify-content:center;color:{_icon_clr};"
                    f"margin:0.2rem 0 0 0.35rem;'>{_nav_svg}</div>",
                    unsafe_allow_html=True,
                )
            with _col_b:
                if st.button(_nav_label, key=f"nav_{_view_id}", use_container_width=True):
                    st.session_state.current_view = _view_id
                    st.rerun()

        st.markdown("<div style='flex:1;'></div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#313244;margin:1rem 0;'>", unsafe_allow_html=True)

        # ── Mi perfil (Sprint 15) — editar las respuestas del onboarding ───────
        import json as _json
        from db.operations import update_user_profile as _upd_profile
        from ui.auth import _PROFESSIONS, _LEARNING_AREAS, _TECH_LEVELS
        from agents.tutor_agent import _parse_tech_level as _ptl
        _up = st.session_state.user_profile
        _area_opts = [a for a in _LEARNING_AREAS if a != "Otro"]
        with st.expander("Mi perfil"):
            with st.form("sidebar_profile_form", clear_on_submit=False):
                # Profesión
                _prof_idx = (
                    _PROFESSIONS.index(_up.get("profession", ""))
                    if _up.get("profession") in _PROFESSIONS
                    else 0
                )
                _new_prof = st.selectbox(
                    "Perfil profesional", _PROFESSIONS, index=_prof_idx, key="sp_prof"
                )
                # Áreas — parsear el valor guardado (comma-separated)
                _cur_areas_raw = _up.get("learning_area", "")
                _cur_areas = (
                    [a.strip() for a in _cur_areas_raw.split(",") if a.strip()]
                    if _cur_areas_raw
                    else []
                )
                _default_areas = [a for a in _cur_areas if a in _area_opts]
                _new_areas = st.multiselect(
                    "Áreas de interés",
                    _area_opts,
                    default=_default_areas,
                    key="sp_areas",
                )
                # Nivel único que se aplica a todas las áreas seleccionadas
                _levels_dict = _ptl(_up.get("tech_level", ""))
                _first_level = next(iter(_levels_dict.values()), "Intermedio") if _levels_dict else "Intermedio"
                _level_idx = _TECH_LEVELS.index(_first_level) if _first_level in _TECH_LEVELS else 1
                _new_level = st.selectbox(
                    "Nivel (para todas las áreas)",
                    _TECH_LEVELS,
                    index=_level_idx,
                    key="sp_level",
                )
                # Sprint 24: meta diaria configurable
                _cur_goal = get_daily_goal(_uid_sidebar)
                _new_goal = st.number_input(
                    "Meta diaria de conceptos",
                    min_value=1,
                    max_value=50,
                    value=_cur_goal,
                    step=1,
                    key="sp_daily_goal",
                )

                # Sprint 26: hora de recordatorio diario por Telegram
                import datetime as _dt
                _cur_reminder = get_reminder_time(_uid_sidebar)
                _rh, _rm = (int(x) for x in _cur_reminder.split(":"))
                _new_reminder = st.time_input(
                    "Hora de recordatorio (Telegram)",
                    value=_dt.time(_rh, _rm),
                    key="sp_reminder_time",
                )

                if st.form_submit_button("Guardar", use_container_width=True, type="primary"):
                    _save_areas = _new_areas if _new_areas else [_area_opts[0]]
                    _save_tech  = _json.dumps(
                        {a: _new_level for a in _save_areas}, ensure_ascii=False
                    )
                    _updated = _upd_profile(
                        _uid_sidebar,
                        profession=_new_prof,
                        learning_area=", ".join(_save_areas),
                        tech_level=_save_tech,
                    )
                    update_daily_goal(_uid_sidebar, int(_new_goal))
                    set_reminder_time(
                        _uid_sidebar,
                        _new_reminder.strftime("%H:%M"),
                    )
                    st.session_state["user"] = _updated
                    st.session_state.user_profile = {
                        "profession":    _new_prof,
                        "learning_area": ", ".join(_save_areas),
                        "tech_level":    _save_tech,
                    }
                    st.success("Perfil actualizado.")
                    st.rerun()

        # ── Vincular Telegram (Sprint 25) ─────────────────────────────────────
        with st.expander("Vincular Telegram"):
            st.markdown(
                "<p style='color:#a6adc8; font-size:0.85rem; margin-bottom:0.75rem;'>"
                "Genera un código y envíalo al bot de Nura en Telegram.</p>",
                unsafe_allow_html=True,
            )
            if st.button("Generar código de vinculación", key="btn_tg_link",
                         use_container_width=True):
                from bot.nura_bridge import generate_link_code as _gen_code
                _code = _gen_code(_uid_sidebar)
                st.session_state["_tg_link_code"] = _code

            if st.session_state.get("_tg_link_code"):
                _c = st.session_state["_tg_link_code"]
                st.code(f"/vincular {_c}", language=None)
                st.markdown(
                    "<p style='color:#6c7086; font-size:0.8rem;'>"
                    "Copia este comando y envíalo al bot de Nura en Telegram. "
                    "El código expira en 10 minutos.</p>",
                    unsafe_allow_html=True,
                )

        # ── Streak indicator ──────────────────────────────────────────────────
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:0.6rem;
                        padding:0.65rem 0.75rem;border-radius:10px;
                        background:#313244;margin-bottom:1rem;">
                <span style="font-size:1.1rem;">🔥</span>
                <span style="font-size:0.875rem;font-weight:600;color:#cdd6f4;">
                    {_streak_sidebar} día{'s' if _streak_sidebar != 1 else ''} seguido{'s' if _streak_sidebar != 1 else ''}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Logout (Lucide log-out icon + text) ───────────────────────────────
        _col_lo_i, _col_lo_b = st.columns([1, 5], gap="small")
        with _col_lo_i:
            st.markdown(
                f"<div style='width:30px;height:30px;display:flex;align-items:center;"
                f"justify-content:center;color:#f38ba8;margin:0.2rem 0 0 0.35rem;'>"
                f"{_SVG_LOGOUT}</div>",
                unsafe_allow_html=True,
            )
        with _col_lo_b:
            if st.button("Cerrar sesión", key="btn_logout", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    # ── Sprint 12: insight adaptativo diario ──────────────────────────────────
    # Se genera una sola vez por día (por sesión Streamlit).
    # Se invoca el grafo con mode='insight' directamente, sin user_input,
    # para que insight_agent analice los patrones del usuario y devuelva un
    # mensaje personalizado que se muestra en un banner antes del chat.
    _uid = _current_user_id()
    today = date.today()
    if st.session_state.get("insight_date") != today:
        try:
            _insight_result = _invoke_with_timeout("", user_id=_uid, mode="insight")
            st.session_state.insight_message = _extract_text(
                _insight_result.get("insight_message")
                or _insight_result.get("response", "")
            )
        except Exception:
            st.session_state.insight_message = ""
        st.session_state.insight_date = today

    if st.session_state.get("insight_message"):
        render_insight_banner(st.session_state.insight_message)

    # ── Despacho de vista según st.session_state.current_view ─────────────────
    _active_view = st.session_state.get("current_view", "descubrir")
    if _active_view == "descubrir":
        _render_view_descubrir()
    elif _active_view == "dominar":
        _render_view_dominar()
    elif _active_view == "conectar":
        _render_view_conectar()
    else:
        _render_view_descubrir()


if __name__ == "__main__":
    main()
