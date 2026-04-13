"""
agents/tutor_agent.py
=====================
Nodo LangGraph que responde preguntas del usuario actuando como tutor
conversacional, usando los conceptos de la BD como contexto personal y,
cuando es necesario, resultados de busqueda web en tiempo real.

Flujo (Sprint 10)
-----------------
1. Clasificacion de necesidad de busqueda: Gemini decide con un prompt
   ligero si la pregunta requiere informacion actualizada (needs_search).
2. Si needs_search=True: llama a web_search() y agrega los snippets como
   contexto adicional al prompt principal.  Las URLs se guardan en
   state.sources para que la UI las muestre al usuario.
3. Si needs_search=False (o la busqueda falla): responde solo con el
   contexto de la BD personal del usuario.

Se activa cuando capture_agent detecta mode='question' o mode='chat'.
En mode='chat' responde sin llamar al LLM (fast-path conversacional).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path


def _parse_tech_level(tech_level_str: str) -> dict[str, str]:
    """
    Convierte el campo tech_level en un dict área → nivel.

    Acepta el nuevo formato JSON (Sprint 15) y el formato legado (cadena simple).
    El resultado se usa en _build_tutor_system_prompt para personalizar el prompt.

    Parámetros
    ----------
    tech_level_str : Valor del campo tech_level leído de la BD o del state.

    Devuelve
    --------
    dict con área → nivel.  Dict vacío si la cadena está vacía.
    """
    if not tech_level_str:
        return {}
    try:
        result = json.loads(tech_level_str)
        if isinstance(result, dict):
            return {str(k): str(v) for k, v in result.items()}
    except (json.JSONDecodeError, ValueError):
        pass
    return {"general": tech_level_str}

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from db.operations import get_all_concepts
from tools.search_tool import web_search
from agents.state import NuraState

# Sprint 19: tools formales disponibles para bind_tools().
# Se importan con try/except para que el módulo siga cargando aunque
# tools/db_tools no esté disponible (compatibilidad con entornos mínimos).
try:
    from tools.db_tools import NURA_TOOLS as _NURA_TOOLS
except ImportError:
    _NURA_TOOLS = []

load_dotenv(Path(__file__).parent.parent / ".env")

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# ── Prompts ────────────────────────────────────────────────────────────────────

CLASSIFY_SYSTEM_PROMPT = (
    "Eres un clasificador de preguntas para un tutor de IA. "
    "Dada una pregunta, responde SOLO con JSON valido con el campo: "
    "needs_search (bool) — true si la pregunta requiere informacion actualizada "
    "sobre herramientas, versiones, eventos recientes, comparaciones o precios. "
    "false si es conceptual, de repaso, o puede responderse con conocimiento general. "
    "Sin texto adicional, solo JSON."
)

TUTOR_SYSTEM_PROMPT = (
    "Eres Nura, tutor adaptativo de aprendizaje amigable y cercano. "
    "El usuario esta aprendiendo IA y tecnologia. "
    "Tienes acceso a su base de conocimiento personal y a resultados de busqueda web "
    "cuando es necesario. "
    "Responde de forma conversacional, maximo 3 parrafos, con ejemplos practicos. "
    "Si usaste web search, al final lista brevemente las fuentes consultadas "
    "con su titulo y URL."
)

# ── Respuestas conversacionales sin LLM (modo 'chat') ─────────────────────────
# Mapa: fragmento normalizado del input → respuesta fija.
# Se recorre en orden; el primer match gana.

def _normalize_chat(text: str) -> str:
    """Normaliza sin tildes y en minúsculas para la tabla de chat."""
    return (
        text.lower()
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ü", "u")
        .replace("ñ", "n")
        .strip()
        .rstrip(".,!¡¿")
    )

_CHAT_RESPONSES: list[tuple[list[str], str]] = [
    # triggers                          # response
    (
        ["no entiendo", "no entendi", "no comprendo",
         "no lo entiendo", "no me quedo claro", "no se nada",
         "estoy perdido", "me perdi"],
        "¿Qué parte no quedó clara? Cuéntame más y te explico de otra manera. 🙂",
    ),
    (
        ["hola", "hey", "buenas", "saludos"],
        "¡Hola! Soy Nura, tu tutor adaptativo. "
        "Puedes escribirme un término para aprender, hacerme una pregunta, "
        "pedir un repaso o iniciar un quiz. ¿Por dónde empezamos?",
    ),
    (
        ["gracias", "thanks", "thankyou"],
        "¡De nada! 😊 Aquí estaré cuando lo necesites. "
        "¿Quieres capturar algo nuevo o profundizar en un concepto?",
    ),
    (
        ["ayuda", "help", "que puedes hacer", "que haces",
         "como me puedes ayudar", "puedes ayudarme", "me puedes ayudar"],
        "Puedo ayudarte con varias cosas:\n"
        "• **Capturar términos** — escribe el concepto y lo registro con clasificación automática.\n"
        "• **Responder preguntas** — hazme cualquier pregunta sobre lo que estás aprendiendo.\n"
        "• **Repaso SM-2** — escribe *repasar* y te sugiero qué revisar hoy.\n"
        "• **Quiz** — escribe *quiz* o *ponme a prueba* para un examen interactivo.\n"
        "¿Qué necesitas?",
    ),
    (
        ["que eres", "quien eres"],
        "Soy **Nura**, un tutor adaptativo con memoria persistente. "
        "Aprendo contigo: guardo los conceptos que capturas, rastreo tu dominio "
        "y programo repasos con el algoritmo SM-2 para que no olvides nada. 🧠",
    ),
    (
        ["adios", "bye", "hasta luego", "chao"],
        "¡Hasta pronto! Sigue aprendiendo. 👋",
    ),
    (
        ["ok", "okay", "vale", "bien", "perfecto", "genial",
         "excelente", "claro", "entendido", "listo", "de acuerdo",
         "si", "sip", "sigamos", "vamos", "empecemos", "empezar", "comenzar"],
        "¡Genial! ¿Qué quieres hacer ahora? "
        "Puedes escribir un término nuevo, hacer una pregunta o pedir un repaso.",
    ),
    (
        ["no"],
        "Sin problema. ¿Hay algo más en lo que pueda ayudarte?",
    ),
    (
        ["no se"],
        "No hay problema, para eso estoy aquí. "
        "¿Quieres que te explique algún concepto o prefieres empezar con un quiz?",
    ),
]


def _chat_response(user_input: str) -> str:
    """
    Devuelve una respuesta conversacional breve sin llamar al LLM.

    Recorre _CHAT_RESPONSES en orden y devuelve la primera respuesta cuyo
    trigger sea una subcadena del input normalizado.  Si ningún trigger
    coincide, devuelve un mensaje genérico de bienvenida.

    Parametros
    ----------
    user_input : Texto del usuario sin espacios iniciales/finales.

    Devuelve
    --------
    str con la respuesta conversacional lista para mostrar al usuario.
    """
    norm = _normalize_chat(user_input)
    for triggers, reply in _CHAT_RESPONSES:
        for trigger in triggers:
            if norm == trigger or norm.startswith(trigger):
                return reply
    # Fallback genérico para cualquier chat no mapeado
    return (
        "¡Hola! Estoy aquí para ayudarte a aprender. "
        "Escribe un término, hazme una pregunta o pide un repaso cuando quieras."
    )


# ── helpers ────────────────────────────────────────────────────────────────────

def _build_knowledge_context(concepts: list) -> str:
    """
    Construye el bloque de contexto con los conceptos del usuario para el prompt.

    Se incluyen solo los campos mas relevantes (termino, categoria, explicacion
    y analogia) para mantener el prompt compacto y dentro de los limites de
    tokens del modelo.  Los conceptos sin explicacion se omiten.

    Parametros
    ----------
    concepts : Lista de Concept cargados desde la BD.

    Devuelve
    --------
    str con el contexto formateado, listo para insertar en el prompt.
    Cadena vacia si no hay conceptos.
    """
    if not concepts:
        return ""

    lines = ["Base de conocimiento del usuario:"]
    for c in concepts:
        if not c.explanation:
            continue
        line = f"- {c.term}"
        if c.category:
            line += f" ({c.category})"
        line += f": {c.explanation[:180]}"
        if c.analogy:
            line += f" — analogia: {c.analogy[:80]}"
        lines.append(line)

    return "\n".join(lines)


def _build_search_context(search_results: list[dict]) -> str:
    """
    Construye el bloque de contexto con los resultados de busqueda web.

    Incluye titulo y snippet de cada resultado para enriquecer el prompt
    del tutor con informacion actualizada.  Las URLs se omiten aqui para
    mantener el prompt conciso; se retornan por separado como fuentes.

    Parametros
    ----------
    search_results : Lista de dicts con title, url, snippet.

    Devuelve
    --------
    str con el contexto de busqueda formateado.
    Cadena vacia si la lista esta vacia.
    """
    if not search_results:
        return ""

    lines = ["Resultados de busqueda web (informacion actualizada):"]
    for i, r in enumerate(search_results, 1):
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        if title or snippet:
            lines.append(f"{i}. {title}: {snippet[:300]}")

    return "\n".join(lines)


def _parse_needs_search(raw: str) -> bool:
    """
    Extrae el valor de needs_search del JSON devuelto por el clasificador.

    Elimina posibles bloques de codigo markdown y parsea el JSON.
    Si el parsing falla, devuelve False como valor seguro (no buscar).

    Parametros
    ----------
    raw : String crudo devuelto por el LLM clasificador.

    Devuelve
    --------
    True si el JSON contiene needs_search=true, False en cualquier otro caso.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        data = json.loads(cleaned)
        return bool(data.get("needs_search", False))
    except (json.JSONDecodeError, ValueError):
        return False


def _is_auth_error(exc: Exception) -> bool:
    """
    Detecta si la excepcion es un error de autenticacion/permiso de la API de Gemini.

    Cubre los casos mas comunes: clave invalida (403/API_KEY_INVALID),
    API no habilitada (SERVICE_DISABLED), permisos insuficientes
    (PERMISSION_DENIED) y acceso prohibido (403 Forbidden).

    Parametros
    ----------
    exc : Excepcion capturada durante la llamada al LLM.

    Devuelve
    --------
    True si el error es de autenticacion/permisos y no tiene sentido reintentar.
    """
    msg = str(exc).upper()
    return any(
        token in msg
        for token in (
            "403",
            "PERMISSION_DENIED",
            "API_KEY_INVALID",
            "SERVICE_DISABLED",
            "INVALID API KEY",
            "API KEY NOT VALID",
            "FORBIDDEN",
        )
    )


def _friendly_api_error(exc: Exception) -> str:
    """
    Convierte una excepcion del LLM en un mensaje amigable para el usuario.

    Parametros
    ----------
    exc : Excepcion capturada durante la llamada al LLM.

    Devuelve
    --------
    str con el mensaje de error legible para el usuario.
    """
    msg = str(exc)
    if _is_auth_error(exc):
        return (
            "No puedo conectarme al servicio de IA en este momento. "
            "Verifica que GOOGLE_API_KEY en el archivo .env sea válida "
            "y que la API de Gemini esté habilitada en tu proyecto de Google Cloud. "
            "(Error 403 / PERMISSION_DENIED)"
        )
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return (
            "El servicio de IA está saturado ahora mismo. "
            "Espera unos minutos y vuelve a intentarlo. 🌙"
        )
    if not os.environ.get("GOOGLE_API_KEY"):
        return (
            "GOOGLE_API_KEY no está configurada. "
            "Agrega tu clave al archivo .env en la raíz del proyecto."
        )
    return f"El servicio de IA no pudo responder: {msg[:200]}"


def _call_gemini(llm: "ChatGoogleGenerativeAI", messages: list, retries: int = 3) -> str:
    """
    Invoca el modelo Gemini con retry ante rate limits transitorios.

    Parametros
    ----------
    llm      : Instancia de ChatGoogleGenerativeAI ya configurada.
    messages : Lista de SystemMessage y HumanMessage para enviar.
    retries  : Numero maximo de intentos (defecto 3).

    Devuelve
    --------
    str con el contenido de la respuesta del modelo.

    Lanza
    -----
    RuntimeError : Si todos los intentos fallan por rate limit.
    PermissionError : Si el error es de autenticacion/permisos (no reintenta).
    Exception    : Cualquier otro error del LLM se repropaga directamente.
    """
    for attempt in range(retries):
        try:
            response = llm.invoke(messages)
            content = response.content
            # content puede ser str, list de content-blocks, u otro objeto
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                # Extraer texto de todos los bloques con clave 'text' o 'content'
                parts: list[str] = []
                for block in content:
                    if isinstance(block, str) and block:
                        parts.append(block)
                    elif isinstance(block, dict):
                        text = block.get("text") or block.get("content", "")
                        if text:
                            parts.append(str(text))
                return " ".join(parts).strip()
            return str(content).strip()
        except Exception as exc:
            if _is_auth_error(exc):
                # Error de autenticacion: no tiene sentido reintentar
                raise PermissionError(_friendly_api_error(exc)) from exc
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                if attempt < retries - 1:
                    time.sleep(15 * (2 ** attempt))  # 15s, 30s
                    continue
            raise
    raise RuntimeError("Gemini fallo tras todos los intentos por rate limit")


# ── Sprint 15: system prompt adaptado al perfil de usuario ────────────────────

# Mapa de profesión → fragmento de ejemplos relevantes para el sistema prompt.
_PROFESSION_EXAMPLES: dict[str, str] = {
    "analista de crédito/banca": (
        "Los ejemplos deben referirse a crédito bancario, NIIF, riesgo crediticio, "
        "provisiones, scoring, regulación prudencial y productos bancarios. "
        "NUNCA uses analogías de tecnología, código, APIs o ingeniería de software."
    ),
    "economista": (
        "Los ejemplos deben referirse a macroeconomía, política monetaria, indicadores "
        "como inflación/PIB/desempleo, mercados financieros, política fiscal y "
        "economía aplicada. "
        "NUNCA uses analogías de tecnología, código, APIs, microservicios o ingeniería."
    ),
    "desarrollador/ingeniero": (
        "Los ejemplos deben referirse a código, arquitecturas de software, APIs, "
        "patrones de diseño, bases de datos y herramientas de ingeniería."
    ),
    "emprendedor/negocios": (
        "Los ejemplos deben referirse a producto, mercado, modelo de negocio, "
        "métricas SaaS, captación de clientes y estrategia empresarial. "
        "NUNCA uses analogías de tecnología o código salvo que el usuario lo pida."
    ),
    "estudiante": (
        "Los ejemplos deben ser conceptuales y académicos, con analogías claras "
        "y comparaciones con materias conocidas."
    ),
    "contador": (
        "Los ejemplos deben referirse a contabilidad, estados financieros, NIIF, "
        "auditoría y tributación. "
        "NUNCA uses analogías de tecnología, código o ingeniería."
    ),
    "abogado": (
        "Los ejemplos deben referirse a contratos, normativa, jurisprudencia y "
        "regulación. NUNCA uses analogías de tecnología o código."
    ),
    "médico": (
        "Los ejemplos deben referirse a diagnóstico, tratamiento, fisiología o "
        "gestión sanitaria. NUNCA uses analogías de tecnología o código."
    ),
}


def _build_tutor_system_prompt(user_profile: dict) -> str:
    """
    Construye el system prompt del tutor personalizado al perfil del usuario.

    Sprint 15 (revisado): lee tech_level como JSON dict o cadena legada via
    _parse_tech_level, y construye una descripción de nivel específica por
    área cuando hay más de una.  Ejemplo de salida:
    "La usuaria es Arquitecta, Avanzado en Finanzas y negocios y Básico en
    IA y tecnología."

    Parámetros
    ----------
    user_profile : Dict con keys profession, learning_area, tech_level.
                   Dict vacío si el onboarding no se completó.

    Devuelve
    --------
    str con el system prompt completo listo para enviar a Gemini.
    """
    profession     = (user_profile.get("profession",    "") or "").strip()
    learning_area  = (user_profile.get("learning_area", "") or "").strip()
    tech_level_raw = (user_profile.get("tech_level",    "") or "").strip()

    # Determinar si el usuario tiene perfil técnico (IA/software) para controlar
    # qué tipo de analogías usa el tutor.
    _la_lower   = learning_area.lower()
    _prof_lower = profession.lower()
    _is_tech = any(
        k in _la_lower
        for k in ("ia y tecnología", "desarrollo de software", "tecnolog", "software", "ia,")
    ) or any(
        k in _prof_lower
        for k in ("desarroll", "ingenier", "developer", "programad", "software", "datos")
    )

    # Base: NO incluye "IA y tecnología" de forma hardcoded — se añade dinámicamente
    # según el área de aprendizaje real del usuario.
    if learning_area and not (profession or learning_area or tech_level_raw):
        context_line = "El usuario está aprendiendo sobre varios temas."
    elif learning_area:
        context_line = f"El usuario está aprendiendo sobre: {learning_area}."
    else:
        context_line = "El usuario está aprendiendo temas de su área profesional."

    base = (
        "Eres Nura, tutor adaptativo de aprendizaje amigable y cercano. "
        f"{context_line} "
        "Tienes acceso a su base de conocimiento personal y a resultados de búsqueda web "
        "cuando es necesario. "
        "Responde de forma conversacional, máximo 3 párrafos, con ejemplos prácticos. "
        "Si usaste web search, al final lista brevemente las fuentes consultadas "
        "con su título y URL."
    )

    if not (profession or learning_area or tech_level_raw):
        return base

    levels_dict = _parse_tech_level(tech_level_raw)

    # Construir descripción de nivel: una entrada para cada área o nivel global
    level_desc = ""
    if levels_dict:
        if len(levels_dict) == 1:
            level_desc = f" de nivel {next(iter(levels_dict.values()))}"
        else:
            lvl_parts = [f"{lvl} en {area}" for area, lvl in levels_dict.items()]
            level_desc = " (" + ", ".join(lvl_parts) + ")"

    profile_parts: list[str] = []
    if profession:
        profile_parts.append(f"El usuario es {profession}{level_desc}.")
    elif level_desc:
        profile_parts.append(f"El usuario tiene nivel{level_desc}.")

    if learning_area:
        areas_list = [a.strip() for a in learning_area.split(",") if a.strip()]
        if len(areas_list) == 1:
            profile_parts.append(f"Su área de interés es {areas_list[0]}.")
        else:
            profile_parts.append(
                f"Sus áreas de interés son: {', '.join(areas_list)}."
            )

    # Busca en el mapa de profesiones la instrucción de ejemplos correspondiente.
    # Se comprueba si ALGUNA palabra clave del mapa está contenida en la profesión.
    profession_lower = profession.lower()
    example_hint = ""

    # Mapa ampliado de palabras clave → llave del dict de profesiones
    _PROF_KEYWORDS: list[tuple[list[str], str]] = [
        (["economista", "econom", "macroeconom", "microeconom"], "economista"),
        (["banca", "crédit", "credit", "analista financiero", "finanzas"], "analista de crédito/banca"),
        (["contador", "contable", "contabilid", "auditor", "tributar"], "contador"),
        (["desarroll", "ingenier", "developer", "programad", "software", "datos", "data"], "desarrollador/ingeniero"),
        (["ux", "diseñ", "design", "experiencia de usuario"], "desarrollador/ingeniero"),
        (["emprend", "negoci", "product manager", "marketing", "ventas"], "emprendedor/negocios"),
        (["estudiant", "student"], "estudiante"),
        (["abogad", "jurista", "legal"], "abogado"),
        (["médic", "doctor", "salud", "enfermer"], "médico"),
    ]
    for keywords, prof_key in _PROF_KEYWORDS:
        if any(kw in profession_lower for kw in keywords):
            example_hint = _PROFESSION_EXAMPLES.get(prof_key, "")
            break

    # Fallback por área de interés cuando la profesión no tiene match
    if not example_hint and learning_area:
        la_lower = learning_area.lower()
        if any(k in la_lower for k in ("finanz", "banca", "crédito", "econom")):
            example_hint = _PROFESSION_EXAMPLES["analista de crédito/banca"]
        elif any(k in la_lower for k in ("software", "tecnolog", "ia y", "desarrollo")):
            example_hint = _PROFESSION_EXAMPLES["desarrollador/ingeniero"]
        elif any(k in la_lower for k in ("marketing", "ventas", "negoci")):
            example_hint = _PROFESSION_EXAMPLES["emprendedor/negocios"]

    # Guardia explícita: si el usuario NO tiene perfil técnico, prohibir analogías tech
    if not _is_tech and not example_hint:
        example_hint = (
            "Usa analogías y ejemplos del mundo real cotidiano o del área del usuario. "
            "NUNCA uses analogías de tecnología, APIs, microservicios, código o ingeniería "
            "de software a menos que el usuario lo pida explícitamente."
        )

    profile_section = " ".join(profile_parts)
    if example_hint:
        profile_section += " " + example_hint

    return base + " " + profile_section


# ── nodo LangGraph ─────────────────────────────────────────────────────────────

def tutor_agent(state: NuraState) -> dict:
    """
    Nodo tutor: responde la pregunta del usuario con contexto de BD y web search.

    Flujo interno (Sprint 10)
    -------------------------
    1. Llama a Gemini con CLASSIFY_SYSTEM_PROMPT para determinar needs_search.
    2. Si needs_search=True:
       a. Llama a web_search(pregunta) para obtener resultados actualizados.
       b. Si la busqueda falla, continua sin fuentes (fallback a BD).
       c. Agrega el contexto de busqueda al prompt del tutor.
       d. Guarda las URLs en sources para la UI.
    3. Construye el contexto de BD (conceptos del usuario).
    4. Llama a Gemini con TUTOR_SYSTEM_PROMPT y el contexto completo.
    5. Devuelve response y sources en el estado.

    El tutor NO persiste nada en la BD — es un nodo de solo lectura.

    Parametros
    ----------
    state : Estado actual del grafo.  Se usa state["user_input"] como pregunta.

    Devuelve
    --------
    dict parcial con response y sources actualizados.

    Lanza
    -----
    EnvironmentError : Si GOOGLE_API_KEY no esta definida.
    RuntimeError     : Si Gemini falla despues de todos los reintentos.
    """
    # ── Fast-path: modo conversacional — sin LLM, sin BD ─────────────────────
    # Si capture_agent detectó mode='chat', respondemos directamente con una
    # respuesta canned para no gastar cuota de API en inputs triviales.
    if state.get("mode") == "chat":
        user_input = state.get("user_input", "").strip()
        return {
            "response": _chat_response(user_input),
            "sources": [],
        }

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {
            "response": (
                "GOOGLE_API_KEY no está configurada. "
                "Agrega tu clave al archivo .env en la raíz del proyecto para "
                "que Nura pueda responder tus preguntas."
            ),
            "sources": [],
        }

    question = state.get("user_input", "").strip()
    user_id: int = state.get("user_id", 1)  # Sprint 11
    sources: list[dict] = []

    # Sprint 15: construir system prompt adaptado al perfil del usuario.
    user_profile: dict = state.get("user_profile") or {}
    tutor_sys_prompt = _build_tutor_system_prompt(user_profile)

    try:
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,  # type: ignore[call-arg]
            temperature=0.3,
        )

        # ── Paso 1: clasificar si la pregunta necesita web search ─────────────
        needs_search = False
        try:
            classify_raw = _call_gemini(
                llm,
                [
                    SystemMessage(content=CLASSIFY_SYSTEM_PROMPT),
                    HumanMessage(content=f"question: {question}"),
                ],
            )
            needs_search = _parse_needs_search(classify_raw)
        except PermissionError:
            # Error de autenticacion en la clasificacion: propagar hacia arriba
            raise
        except Exception:
            # Cualquier otro fallo en la clasificacion → continuar sin busqueda
            needs_search = False

        # ── Paso 2: busqueda web si es necesaria ──────────────────────────────
        search_ctx = ""
        if needs_search:
            search_result = web_search(question)
            raw_results = search_result.get("results", [])
            if raw_results:
                sources = raw_results
                search_ctx = _build_search_context(raw_results)

        # ── Paso 3: construir contexto de BD ──────────────────────────────────
        concepts = get_all_concepts(user_id=user_id)
        knowledge_ctx = _build_knowledge_context(concepts)

        # ── Paso 4: construir el mensaje completo ─────────────────────────────
        human_parts: list[str] = []
        if knowledge_ctx:
            human_parts.append(knowledge_ctx)
            human_parts.append("")
        if search_ctx:
            human_parts.append(search_ctx)
            human_parts.append("")
        human_parts.append(f"Pregunta: {question}")
        human_text = "\n".join(human_parts)

        # Temperatura mas alta para respuestas conversacionales.
        # Sprint 19: bind_tools() registra los tools para que Gemini pueda
        # decidir invocarlos dinámicamente si el contexto lo requiere.
        llm_tutor = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,  # type: ignore[call-arg]
            temperature=0.7,
        )
        if _NURA_TOOLS:
            llm_tutor = llm_tutor.bind_tools(_NURA_TOOLS)

        tutor_response = _call_gemini(
            llm_tutor,
            [
                SystemMessage(content=tutor_sys_prompt),
                HumanMessage(content=human_text),
            ],
        )

        # ── Paso 5: generar diagrama SVG si el contenido lo amerita ──────────
        # Se envuelve en try/except para no bloquear la respuesta del tutor
        # si diagram_tool falla por cualquier motivo (cuota, timeout, etc.).
        diagram_svg = ""
        try:
            from tools.diagram_tool import should_generate_diagram, generate_diagram_svg
            if should_generate_diagram(tutor_response, user_profile):
                # Reutilizar el mismo llm para determinar el tipo antes de
                # llamar generate_diagram_svg (que lo determina internamente
                # al generar nodos/aristas, así que pasamos 'flow' como default
                # seguro y dejamos que Gemini ajuste la estructura).
                from tools.diagram_tool import _call_gemini_json as _dgj
                _snip = tutor_response.strip()[:600]
                _dp = (
                    f'El siguiente texto de explicación se beneficiaría de un diagrama visual? '
                    f'Texto: "{_snip}". '
                    f'Responde SOLO con JSON válido: '
                    f'{{"needs_diagram": true, '
                    f'"diagram_type": "flow|hierarchy|comparison|cycle", '
                    f'"reason": "motivo breve"}}'
                )
                try:
                    _dtype = _dgj(_dp).get("diagram_type", "flow")
                except Exception:
                    _dtype = "flow"
                diagram_svg = generate_diagram_svg(tutor_response, _dtype)
        except Exception:
            diagram_svg = ""

        # ── Paso 6: detectar conceptos nuevos en la respuesta ────────────────
        # Sugiere al usuario agregar términos técnicos mencionados en la
        # respuesta que aún no están en su mapa de conocimiento.
        # Se envuelve en try/except — si falla, continúa sin sugerencias.
        suggested_concepts: list[str] = []
        try:
            from tools.concept_detector_tool import detect_new_concepts
            existing_terms = [c.term for c in concepts]
            suggested_concepts = detect_new_concepts(
                tutor_response,
                existing_terms,
                user_id=user_id,
            )
        except Exception:
            suggested_concepts = []

        return {
            "response":           tutor_response,
            "sources":            sources,
            "diagram_svg":        diagram_svg,
            "suggested_concepts": suggested_concepts,
        }

    except Exception as exc:
        return {
            "response":           _friendly_api_error(exc),
            "sources":            [],
            "diagram_svg":        "",
            "suggested_concepts": [],
        }
