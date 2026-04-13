"""
ui/auth.py
==========
Página de autenticación de Nura — login, registro y onboarding de usuarios.

render_login_page() muestra un formulario con dos pestañas:
  - "Iniciar sesión": valida credenciales con authenticate_user().
  - "Registrarse": crea una cuenta nueva con create_user().

render_onboarding(user) muestra el flujo de onboarding de 4 pasos:
  0. Bienvenida — pantalla motivadora con las tres propuestas de valor.
  1. Profesión — radio buttons con campo libre si elige "Otro".
  2. Áreas de aprendizaje — multiselect con campo libre si incluye "Otro".
  3. Nivel por área — un radio por cada área seleccionada en el Paso 2.

El campo learning_area se guarda como string separado por comas.
El campo tech_level se guarda como JSON serializado: {"área": "nivel", …}.

Nunca almacena ni registra contraseñas en texto plano.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.models import User


def render_login_page() -> "User | None":
    """
    Renderiza la página de autenticación con pestañas login/registro.

    Flujo de login
    --------------
    1. El usuario escribe su nombre de usuario y contraseña.
    2. Al hacer clic en "Entrar", llama a authenticate_user().
    3. Si las credenciales son correctas, guarda el User en
       st.session_state["user"] y devuelve el User.
    4. Si son incorrectas, muestra un mensaje de error y devuelve None.

    Flujo de registro
    -----------------
    1. El usuario escribe username, contraseña y confirmación.
    2. Se valida que los campos no estén vacíos y que las contraseñas coincidan.
    3. Al hacer clic en "Crear cuenta", llama a create_user().
    4. Si tiene éxito, inicia sesión automáticamente con el nuevo User.
    5. Si el username ya existe, muestra un mensaje de error descriptivo.

    Devuelve
    --------
    User si el login o registro fue exitoso, None en caso contrario.
    """
    import streamlit as st
    from db.operations import authenticate_user, create_user

    # ── Cabecera: NuraLogo centrado (mismo diseño que el sidebar) ─────────────
    st.markdown(
        """
        <div style="display:flex; flex-direction:column; align-items:center;
                    padding: 2.5rem 1rem 1.75rem 1rem;">

          <!-- N bold + constelación SVG -->
          <div style="display:flex; align-items:center; gap:4px; margin-bottom:4px;">
            <span style="font-size:3rem; font-weight:900; color:#60a0ff;
                         line-height:1; font-family:'Segoe UI',system-ui,sans-serif;">N</span>
            <svg width="48" height="40" viewBox="0 0 32 28" fill="none"
                 style="margin-left:2px; margin-bottom:3px;">
              <!-- líneas de conexión finas en gris -->
              <line x1="4"  y1="14" x2="12" y2="8"  stroke="#6c7086" stroke-width="0.7"/>
              <line x1="12" y1="8"  x2="22" y2="12" stroke="#6c7086" stroke-width="0.7"/>
              <line x1="22" y1="12" x2="28" y2="6"  stroke="#6c7086" stroke-width="0.7"/>
              <line x1="12" y1="8"  x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
              <line x1="22" y1="12" x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
              <!-- nodos coloreados: amarillo, morado, verde, teal, rosa -->
              <circle cx="4"  cy="14" r="2.5" fill="#f9e2af"/>
              <circle cx="12" cy="8"  r="3"   fill="#cba6f7"/>
              <circle cx="22" cy="12" r="2.5" fill="#a6e3a1"/>
              <circle cx="28" cy="6"  r="2"   fill="#74c7ec"/>
              <circle cx="16" cy="20" r="2.5" fill="#f38ba8"/>
            </svg>
          </div>

          <!-- Texto "Nura" -->
          <span style="font-size:1.4rem; font-weight:600; color:#cdd6f4;
                       letter-spacing:0.01em; margin-top:-6px;">Nura</span>

          <!-- Subtítulo -->
          <span style="font-size:0.7rem; color:#6c7086; letter-spacing:0.12em;
                       margin-top:4px; text-transform:lowercase;">
            aprende · conecta · domina
          </span>

          <!-- Tagline de login -->
          <p style="color:#7f849c; font-size:0.9rem; margin:1.25rem 0 0 0;
                    text-align:center;">
            Tu sistema de aprendizaje adaptativo con memoria persistente
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Contenedor centrado de ancho limitado
    col_l, col_c, col_r = st.columns([1, 2, 1])

    with col_c:
        tab_login, tab_register = st.tabs(["Iniciar sesión", "Registrarse"])

        # ── Tab login ─────────────────────────────────────────────────────────
        with tab_login:
            with st.form("form_login", clear_on_submit=False):
                st.markdown(
                    "<p style='color:#a6adc8; font-size:0.9rem; margin-bottom:1rem;'>"
                    "Bienvenido de vuelta. Ingresa tus credenciales.</p>",
                    unsafe_allow_html=True,
                )
                username_login = st.text_input(
                    "Usuario",
                    placeholder="tu_nombre_de_usuario",
                    key="login_username",
                )
                password_login = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="••••••••",
                    key="login_password",
                )
                submitted_login = st.form_submit_button(
                    "Entrar →",
                    use_container_width=True,
                    type="primary",
                )

            if submitted_login:
                if not username_login.strip():
                    st.error("El nombre de usuario no puede estar vacío.")
                elif not password_login:
                    st.error("La contraseña no puede estar vacía.")
                else:
                    user = authenticate_user(username_login.strip(), password_login)
                    if user is None:
                        st.error("Usuario o contraseña incorrectos. Inténtalo de nuevo.")
                    else:
                        st.session_state["user"] = user
                        st.success(f"¡Bienvenido, {user.username}!")
                        st.rerun()

        # ── Tab registro ──────────────────────────────────────────────────────
        with tab_register:
            with st.form("form_register", clear_on_submit=True):
                st.markdown(
                    "<p style='color:#a6adc8; font-size:0.9rem; margin-bottom:1rem;'>"
                    "Crea tu cuenta para empezar a aprender con Nura.</p>",
                    unsafe_allow_html=True,
                )
                username_reg = st.text_input(
                    "Nombre de usuario",
                    placeholder="elige_un_usuario",
                    key="reg_username",
                )
                password_reg = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="mínimo 6 caracteres",
                    key="reg_password",
                )
                password_confirm = st.text_input(
                    "Confirmar contraseña",
                    type="password",
                    placeholder="repite tu contraseña",
                    key="reg_password_confirm",
                )
                submitted_register = st.form_submit_button(
                    "Crear cuenta →",
                    use_container_width=True,
                    type="primary",
                )

            if submitted_register:
                errors = _validate_registration(
                    username_reg, password_reg, password_confirm
                )
                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    try:
                        user = create_user(username_reg.strip(), password_reg)
                        st.session_state["user"] = user
                        st.success(
                            f"¡Cuenta creada! Bienvenido, {user.username}."
                        )
                        st.rerun()
                    except ValueError as exc:
                        # Username ya existe u otro error de negocio
                        st.error(str(exc))

    return st.session_state.get("user")


_PROFESSIONS = [
    "Analista de crédito/banca",
    "Desarrollador/ingeniero",
    "Emprendedor/negocios",
    "Estudiante",
    "Otro",
]

_LEARNING_AREAS = [
    "IA y tecnología",
    "Finanzas y negocios",
    "Desarrollo de software",
    "Marketing y ventas",
    "Otro",
]

_TECH_LEVELS = ["Básico", "Intermedio", "Avanzado"]

# SVG Lucide inline (stroke=currentColor, 20×20, fill=none, stroke-width=1.75)
_SVG_COMPASS = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"'
    ' fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"'
    ' stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="10"/>'
    '<polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>'
    "</svg>"
)
_SVG_LAYERS = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"'
    ' fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"'
    ' stroke-linejoin="round">'
    '<polygon points="12 2 2 7 12 12 22 7 12 2"/>'
    '<polyline points="2 17 12 22 22 17"/>'
    '<polyline points="2 12 12 17 22 12"/>'
    "</svg>"
)
_SVG_NETWORK = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"'
    ' fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"'
    ' stroke-linejoin="round">'
    '<rect x="16" y="16" width="6" height="6" rx="1"/>'
    '<rect x="2" y="16" width="6" height="6" rx="1"/>'
    '<rect x="9" y="2" width="6" height="6" rx="1"/>'
    '<path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3"/>'
    '<path d="M12 12V8"/>'
    "</svg>"
)
_SVG_BRAIN = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"'
    ' fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"'
    ' stroke-linejoin="round">'
    '<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.46 2.5 2.5 0 0 1-1.7'
    "-2.3 2.5 2.5 0 0 1-1.32-4.24 3 3 0 0 1 .34-5.58 2.5 2.5 0 0 1 1.64-4.43Z\"/>"
    '<path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.46 2.5 2.5 0 0 0'
    " 1.7-2.3 2.5 2.5 0 0 0 1.32-4.24 3 3 0 0 0-.34-5.58 2.5 2.5 0 0 0-1.64-4.43Z\"/>"
    "</svg>"
)


# ── Logo SVG reutilizable (compacto, solo la figura) ──────────────────────────
_NURA_LOGO_SMALL = """
  <div style="display:flex; align-items:center; gap:4px; margin-bottom:4px;">
    <span style="font-size:2.5rem; font-weight:900; color:#60a0ff;
                 line-height:1; font-family:'Segoe UI',system-ui,sans-serif;">N</span>
    <svg width="40" height="34" viewBox="0 0 32 28" fill="none"
         style="margin-left:2px; margin-bottom:2px;">
      <line x1="4"  y1="14" x2="12" y2="8"  stroke="#6c7086" stroke-width="0.7"/>
      <line x1="12" y1="8"  x2="22" y2="12" stroke="#6c7086" stroke-width="0.7"/>
      <line x1="22" y1="12" x2="28" y2="6"  stroke="#6c7086" stroke-width="0.7"/>
      <line x1="12" y1="8"  x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
      <line x1="22" y1="12" x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
      <circle cx="4"  cy="14" r="2.5" fill="#f9e2af"/>
      <circle cx="12" cy="8"  r="3"   fill="#cba6f7"/>
      <circle cx="22" cy="12" r="2.5" fill="#a6e3a1"/>
      <circle cx="28" cy="6"  r="2"   fill="#74c7ec"/>
      <circle cx="16" cy="20" r="2.5" fill="#f38ba8"/>
    </svg>
  </div>
"""


def _ob_header() -> None:
    """Renderiza la cabecera con logo Nura centrado usada en todos los pasos.

    El logo SVG de la constelación, la letra N y el texto 'Nura' se emiten
    en un ÚNICO bloque st.markdown con unsafe_allow_html=True para garantizar
    que el HTML se renderice correctamente y no aparezca como texto literal.
    """
    import streamlit as st

    # Todo el HTML está en línea (sin f-string ni interpolación de variables)
    # para evitar que el parser de Python o el de Streamlit modifique algún
    # carácter y cause que los tags aparezcan como texto visible.
    st.markdown(
        """
        <div style="display:flex; flex-direction:column; align-items:center;
                    padding: 1.5rem 1rem 0.75rem 1rem;">
          <div style="display:flex; align-items:center; gap:4px; margin-bottom:4px;">
            <span style="font-size:2.5rem; font-weight:900; color:#60a0ff;
                         line-height:1;
                         font-family:'Segoe UI',system-ui,sans-serif;">N</span>
            <svg width="40" height="34" viewBox="0 0 32 28" fill="none"
                 style="margin-left:2px; margin-bottom:2px;">
              <line x1="4"  y1="14" x2="12" y2="8"  stroke="#6c7086" stroke-width="0.7"/>
              <line x1="12" y1="8"  x2="22" y2="12" stroke="#6c7086" stroke-width="0.7"/>
              <line x1="22" y1="12" x2="28" y2="6"  stroke="#6c7086" stroke-width="0.7"/>
              <line x1="12" y1="8"  x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
              <line x1="22" y1="12" x2="16" y2="20" stroke="#6c7086" stroke-width="0.7"/>
              <circle cx="4"  cy="14" r="2.5" fill="#f9e2af"/>
              <circle cx="12" cy="8"  r="3"   fill="#cba6f7"/>
              <circle cx="22" cy="12" r="2.5" fill="#a6e3a1"/>
              <circle cx="28" cy="6"  r="2"   fill="#74c7ec"/>
              <circle cx="16" cy="20" r="2.5" fill="#f38ba8"/>
            </svg>
          </div>
          <span style="font-size:1.15rem; font-weight:600; color:#cdd6f4;
                       letter-spacing:0.01em; margin-top:-4px;">Nura</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_onboarding(user: "User") -> bool:
    """
    Renderiza el flujo de onboarding de 4 pasos para personalizar el perfil.

    Sprint 15 (revisado): se muestra tras el primer registro o cuando el usuario
    tiene alguno de los tres campos de perfil vacíos.  Usa
    st.session_state.onboarding_step para controlar el paso activo.

    Pasos
    -----
    0 — Bienvenida: pantalla motivadora con las tres propuestas de valor.
    1 — Profesión: radio buttons; "Otro" → text_input libre.
    2 — Áreas de aprendizaje: multiselect; "Otro" → text_input libre.
        Guarda como string separado por comas en ob_areas_str.
    3 — Nivel por área: un radio button por cada área seleccionada.
        Guarda como JSON serializado en tech_level.

    Parámetros
    ----------
    user : User autenticado al que se le asignará el perfil.

    Devuelve
    --------
    True si el onboarding acaba de completarse en esta llamada,
    False mientras sigue en curso.
    """
    import json
    import streamlit as st
    from db.operations import update_user_profile

    step: int = st.session_state.get("onboarding_step", 0)

    _ob_header()

    # ── Barra de progreso (visible en todos los pasos) ─────────────────────────
    # Paso 0 = bienvenida (sin número de paso), pasos 1-3 = preguntas.
    if step == 0:
        st.progress(0.0)
    else:
        st.progress((step - 1) / 3, text=f"Paso {step} de 3")

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:

        # ── Paso 0: Bienvenida ─────────────────────────────────────────────────
        if step == 0:
            # unsafe_allow_html=True es obligatorio para que los SVG y el HTML
            # de las tarjetas se rendericen correctamente en vez de mostrarse
            # como texto literal.
            st.markdown(
                f"""
                <div style="text-align:center; padding: 0.5rem 0 1.5rem 0;">
                  <h2 style="color:#cdd6f4; font-weight:700; margin-bottom:0.25rem;">
                    Bienvenido/a a Nura
                  </h2>
                  <p style="color:#7f849c; font-size:0.95rem; margin-bottom:2rem;">
                    Tu tutor personal con memoria.
                  </p>
                </div>
                <div style="display:flex; flex-direction:column; gap:1rem;
                            margin-bottom:2rem;">
                  <!-- Descubrir -->
                  <div style="display:flex; align-items:flex-start; gap:0.85rem;
                               background:#313244; border-radius:10px;
                               padding:0.9rem 1rem;">
                    <span style="color:#60a0ff; flex-shrink:0; margin-top:1px;">
                      {_SVG_COMPASS}
                    </span>
                    <div>
                      <span style="color:#cdd6f4; font-weight:600;
                                   font-size:0.95rem;">Descubrir</span>
                      <p style="color:#a6adc8; font-size:0.85rem; margin:0.2rem 0 0 0;">
                        Escribe cualquier término o pregunta durante el día y Nura lo
                        convierte en conocimiento estructurado.
                      </p>
                    </div>
                  </div>
                  <!-- Dominar -->
                  <div style="display:flex; align-items:flex-start; gap:0.85rem;
                               background:#313244; border-radius:10px;
                               padding:0.9rem 1rem;">
                    <span style="color:#cba6f7; flex-shrink:0; margin-top:1px;">
                      {_SVG_LAYERS}
                    </span>
                    <div>
                      <span style="color:#cdd6f4; font-weight:600;
                                   font-size:0.95rem;">Dominar</span>
                      <p style="color:#a6adc8; font-size:0.85rem; margin:0.2rem 0 0 0;">
                        Repasa con flashcards inteligentes que se adaptan a ti y
                        aparecen justo cuando las necesitas.
                      </p>
                    </div>
                  </div>
                  <!-- Quiz -->
                  <div style="display:flex; align-items:flex-start; gap:0.85rem;
                               background:#313244; border-radius:10px;
                               padding:0.9rem 1rem;">
                    <span style="color:#f9e2af; flex-shrink:0; margin-top:1px;">
                      {_SVG_BRAIN}
                    </span>
                    <div>
                      <span style="color:#cdd6f4; font-weight:600;
                                   font-size:0.95rem;">Quiz</span>
                      <p style="color:#a6adc8; font-size:0.85rem; margin:0.2rem 0 0 0;">
                        Pon a prueba lo que aprendiste con preguntas generadas
                        automáticamente según tu nivel.
                      </p>
                    </div>
                  </div>
                  <!-- Conectar -->
                  <div style="display:flex; align-items:flex-start; gap:0.85rem;
                               background:#313244; border-radius:10px;
                               padding:0.9rem 1rem;">
                    <span style="color:#a6e3a1; flex-shrink:0; margin-top:1px;">
                      {_SVG_NETWORK}
                    </span>
                    <div>
                      <span style="color:#cdd6f4; font-weight:600;
                                   font-size:0.95rem;">Conectar</span>
                      <p style="color:#a6adc8; font-size:0.85rem; margin:0.2rem 0 0 0;">
                        Visualiza tu conocimiento como una constelación que crece con
                        cada concepto nuevo que aprendes.
                      </p>
                    </div>
                  </div>
                </div>
                <p style="color:#cdd6f4; font-size:1.1rem; text-align:center;
                           font-style:italic; margin-bottom:1.25rem;">
                  Cuanto más uses Nura, más te conoce.<br/>
                  Y cuanto más te conoce, mejor te enseña.
                </p>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Empezar →",
                type="primary",
                use_container_width=True,
                key="ob_start",
            ):
                st.session_state["onboarding_step"] = 1
                st.rerun()

        # ── Paso 1: Profesión ──────────────────────────────────────────────────
        elif step == 1:
            st.markdown(
                "<h4 style='color:#cdd6f4; margin-bottom:0.5rem;'>"
                "¿Cuál es tu perfil profesional?</h4>",
                unsafe_allow_html=True,
            )
            profession = st.radio(
                "Selecciona el que más se acerca a tu rol:",
                _PROFESSIONS,
                index=0,
                key="ob_profession_radio",
                label_visibility="collapsed",
            )
            profession_custom = ""
            if profession == "Otro":
                profession_custom = st.text_input(
                    "Escribe tu profesión:",
                    placeholder="p. ej. Consultor, Periodista, Médico…",
                    key="ob_profession_custom",
                )
            st.markdown("<br/>", unsafe_allow_html=True)
            if st.button(
                "Siguiente →",
                type="primary",
                use_container_width=True,
                key="ob_next_1",
            ):
                final = profession_custom.strip() if profession == "Otro" else profession
                st.session_state["ob_profession"] = final or "Otro"
                st.session_state["onboarding_step"] = 2
                st.rerun()

        # ── Paso 2: Áreas de aprendizaje (multiselect) ────────────────────────
        elif step == 2:
            st.markdown(
                "<h4 style='color:#cdd6f4; margin-bottom:0.5rem;'>"
                "¿En qué áreas quieres enfocarte?</h4>",
                unsafe_allow_html=True,
            )
            # Opciones del multiselect: todas menos "Otro"
            _area_opts = [a for a in _LEARNING_AREAS if a != "Otro"]
            selected_areas = st.multiselect(
                "Selecciona una o más áreas:",
                _area_opts,
                default=[_area_opts[0]],
                key="ob_areas_multi",
                label_visibility="collapsed",
            )
            # Añadir área personalizada si elige "Otro"
            include_other = st.checkbox(
                "Otra área no listada",
                key="ob_areas_other_cb",
            )
            area_custom = ""
            if include_other:
                area_custom = st.text_input(
                    "Escribe el área:",
                    placeholder="p. ej. Ciencias de la salud, Derecho, Arte…",
                    key="ob_area_custom",
                )
            st.markdown("<br/>", unsafe_allow_html=True)
            col_back, col_next = st.columns(2, gap="small")
            with col_back:
                if st.button("← Atrás", use_container_width=True, key="ob_back_2"):
                    st.session_state["onboarding_step"] = 1
                    st.rerun()
            with col_next:
                if st.button(
                    "Siguiente →",
                    type="primary",
                    use_container_width=True,
                    key="ob_next_2",
                ):
                    all_areas = list(selected_areas)
                    if include_other and area_custom.strip():
                        all_areas.append(area_custom.strip())
                    # Si no eligió nada, usar la primera opción como fallback
                    if not all_areas:
                        all_areas = [_area_opts[0]]
                    st.session_state["ob_areas"] = all_areas
                    st.session_state["onboarding_step"] = 3
                    st.rerun()

        # ── Paso 3: Nivel por área ─────────────────────────────────────────────
        elif step == 3:
            saved_areas: list[str] = st.session_state.get("ob_areas", [_LEARNING_AREAS[0]])
            st.markdown(
                "<h4 style='color:#cdd6f4; margin-bottom:0.5rem;'>"
                "¿Cuál es tu nivel en cada área?</h4>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='color:#a6adc8; font-size:0.85rem; margin-bottom:1rem;'>"
                "Selecciona tu nivel de experiencia para cada área que elegiste.</p>",
                unsafe_allow_html=True,
            )
            # Renderizar un radio por área, con key indexada para evitar colisiones
            for idx, area in enumerate(saved_areas):
                st.markdown(
                    f"<p style='color:#cdd6f4; font-size:0.9rem; font-weight:600;"
                    f"margin-bottom:0.2rem;'>{area}</p>",
                    unsafe_allow_html=True,
                )
                st.radio(
                    f"Nivel en {area}:",
                    _TECH_LEVELS,
                    index=1,  # "Intermedio" por defecto
                    key=f"ob_level_{idx}",
                    horizontal=True,
                    label_visibility="collapsed",
                )
                st.markdown("<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True)

            st.markdown("<br/>", unsafe_allow_html=True)
            col_back, col_start = st.columns(2, gap="small")
            with col_back:
                if st.button("← Atrás", use_container_width=True, key="ob_back_3"):
                    st.session_state["onboarding_step"] = 2
                    st.rerun()
            with col_start:
                if st.button(
                    "Empezar con Nura →",
                    type="primary",
                    use_container_width=True,
                    key="ob_finish",
                ):
                    # Leer los niveles de session_state por índice
                    levels_dict: dict[str, str] = {}
                    for idx, area in enumerate(saved_areas):
                        levels_dict[area] = st.session_state.get(
                            f"ob_level_{idx}", "Intermedio"
                        )
                    saved_profession = st.session_state.get(
                        "ob_profession", _PROFESSIONS[0]
                    )
                    saved_learning_area = ", ".join(saved_areas)
                    saved_tech_level    = json.dumps(levels_dict, ensure_ascii=False)

                    updated_user = update_user_profile(
                        user.id,
                        profession=saved_profession,
                        learning_area=saved_learning_area,
                        tech_level=saved_tech_level,
                    )
                    st.session_state["user"] = updated_user
                    # Limpiar estado temporal del onboarding
                    for _k in (
                        "onboarding_step", "ob_profession", "ob_areas",
                        "ob_areas_other_cb", "ob_area_custom",
                    ):
                        st.session_state.pop(_k, None)
                    # Limpiar claves de nivel dinámicas
                    for idx in range(len(saved_areas)):
                        st.session_state.pop(f"ob_level_{idx}", None)
                    st.rerun()
                    return True

    return False


def _validate_registration(
    username: str,
    password: str,
    password_confirm: str,
) -> list[str]:
    """
    Valida los campos del formulario de registro y devuelve la lista de errores.

    Reglas de validación
    --------------------
    - username no puede estar vacío.
    - username debe tener entre 3 y 64 caracteres.
    - username solo puede contener letras, números, guiones y puntos.
    - password debe tener al menos 6 caracteres.
    - password y password_confirm deben coincidir.

    Parámetros
    ----------
    username         : Valor del campo usuario.
    password         : Valor del campo contraseña.
    password_confirm : Valor del campo confirmación.

    Devuelve
    --------
    Lista de strings con los mensajes de error.  Vacía si no hay errores.
    """
    import re

    errors: list[str] = []

    username = username.strip()

    if not username:
        errors.append("El nombre de usuario no puede estar vacío.")
    elif len(username) < 3:
        errors.append("El nombre de usuario debe tener al menos 3 caracteres.")
    elif len(username) > 64:
        errors.append("El nombre de usuario no puede tener más de 64 caracteres.")
    elif not re.match(r"^[a-zA-Z0-9_.\-]+$", username):
        errors.append(
            "El nombre de usuario solo puede contener letras, números, _, . y -."
        )

    if len(password) < 6:
        errors.append("La contraseña debe tener al menos 6 caracteres.")

    if password != password_confirm:
        errors.append("Las contraseñas no coinciden.")

    return errors
