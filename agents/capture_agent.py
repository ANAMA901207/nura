"""
agents/capture_agent.py
=======================
Primer nodo del grafo LangGraph: interpreta el input del usuario y lo
clasifica en uno de ocho modos antes de decidir la ruta del pipeline.

Modos detectados (en orden de prioridad)
-----------------------------------------
0. 'chat'        — expresión conversacional corta (saludo, confirmación,
                   "no entiendo", "ayuda", etc.).  No toca la BD.
                   El grafo redirige al tutor para una respuesta breve.
1. 'quiz'        — el usuario quiere un quiz de opción múltiple.
                   Palabras clave: quiz, examen, ponme a prueba, test...
2. 'review'      — el usuario quiere repasar conceptos existentes.
                   Palabras clave: repasar, repaso, revisar, revisión...
3. 'question'    — el usuario hace una pregunta sobre un concepto.
                   Indicadores: '?', palabras interrogativas (qué, cómo...).
4. 'reclassify'  — el término ya existe en la BD pero aún no está clasificado
                   (is_classified=False).  Se reutiliza el concepto existente
                   y se envía al clasificador sin crear un duplicado.
4a.'spelling'    — Sprint 14: el término parece tener un error ortográfico.
                   Gemini sugiere la corrección; la UI pregunta al usuario.
4b.'clarify'     — Sprint 14: el término es ambiguo (p. ej. 'cursor', 'python').
                   Gemini devuelve 2-3 significados; la UI pide al usuario elegir.
5. 'capture'     — el usuario introduce un término nuevo para aprender.
                   Caso por defecto: se guarda con save_concept().

Las prioridades 0-4 usan heurísticas de palabras clave sin llamar a ningún
modelo.  Las prioridades 4a-4b llaman a Gemini; si el API falla se pasa
directamente a captura para no bloquear al usuario.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from db.operations import get_all_concepts, get_concept_by_term, save_concept
from agents.state import NuraState

# Sprint 19: tools formales disponibles para bind_tools() en invocaciones
# externas y para registro en ToolNode del grafo.
try:
    from tools.db_tools import NURA_TOOLS as _NURA_TOOLS  # noqa: F401
except ImportError:
    _NURA_TOOLS = []

load_dotenv(Path(__file__).parent.parent / ".env")


# ── Detección de modo chat (Prioridad 0) ──────────────────────────────────────

def _normalize(text: str) -> str:
    """Normaliza a minúsculas sin tildes para comparaciones heurísticas."""
    return (
        text.lower()
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ü", "u")
        .replace("ñ", "n")
        .strip()
        .rstrip(".,!¡¿")
    )


# Palabras que por sí solas (input de 1 token) son conversacionales.
_CHAT_SINGLE_WORDS = {
    "hola", "hey", "buenas", "saludos",
    "ok", "okay", "vale", "bien", "perfecto", "genial", "excelente",
    "si", "sip", "no", "nop",
    "gracias", "thanks", "thankyou",
    "claro", "entendido", "listo", "de acuerdo",
    "ayuda", "help",
    "adios", "bye", "hasta luego", "chao",
}

# Frases cortas que se detectan como expresión conversacional (≤ 6 palabras).
_CHAT_PHRASES = [
    "no entiendo",
    "no entendi",
    "no lo entiendo",
    "no entiendo nada",
    "no comprendo",
    "no me quedo claro",
    "que puedes hacer",
    "que haces",
    "que eres",
    "quien eres",
    "para que sirves",
    "como me puedes ayudar",
    "como funciona esto",       # "esto" indica contexto conversacional, no concepto
    "me puedes ayudar",
    "puedes ayudarme",
    "no se",
    "no se nada",
    "estoy perdido",
    "me perdi",
    "empecemos",
    "empezar",
    "comenzar",
    "vamos",
    "sigamos",
]


def _is_chat(text: str) -> bool:
    """
    Determina si el input es una expresión conversacional corta.

    Se activa como Prioridad 0 para evitar que saludos, confirmaciones o
    frases de ayuda sean tratados como términos a capturar o preguntas al tutor.

    Criterios
    ---------
    1. El input tiene 6 palabras o menos (inputs más largos se dejan pasar).
    2. El texto normalizado coincide con una palabra o frase de las listas.
    3. Excepción: si el input tiene MÁS de 4 palabras y empieza con una
       expresión de pregunta implícita (ej. "no entiendo qué es blockchain"),
       se devuelve False para que _is_question lo clasifique correctamente.
       Esto evita que frases-pregunta largas reciban respuestas canned cortas
       en lugar de una explicación real del tutor.

    Parametros
    ----------
    text : Input del usuario, ya sin espacios iniciales/finales.

    Devuelve
    --------
    True si el texto es claramente conversacional.
    """
    norm = _normalize(text)
    words = norm.split()

    # Solo evaluar inputs cortos para no capturar accidentalmente conceptos
    if len(words) > 6:
        return False

    # Coincidencia exacta con palabra individual
    if len(words) == 1 and words[0] in _CHAT_SINGLE_WORDS:
        return True

    # Coincidencia con frases conocidas — para inputs de 5-6 palabras, solo
    # usar coincidencia exacta si la frase comienza con una expresión de pregunta,
    # ya que "no entiendo X" con X específico merece respuesta del tutor, no canned.
    for phrase in _CHAT_PHRASES:
        if norm == phrase or norm.startswith(phrase):
            if len(words) > 4 and norm != phrase:
                # Input largo que solo empieza con la frase → dejar pasar a _is_question
                continue
            return True

    return False


# ── Detección de modo quiz ────────────────────────────────────────────────────

_QUIZ_WORDS = {
    "quiz", "examen", "test", "prueba", "evaluacion", "evaluación",
    "ejercicio", "ejercicios",
}

_QUIZ_PHRASES = [
    "ponme a prueba", "hazme un quiz", "hazme un test", "hazme un examen",
    "modo quiz", "iniciar quiz", "quiero un quiz", "quiero un test",
    "modo examen", "quiero que me evalues", "quiero que me evalúes",
    "pon a prueba", "a prueba",
]


def _is_quiz(text: str) -> bool:
    """
    Determina si el input solicita un quiz de opcion multiple.

    Busca primero frases completas (mayor precision) y luego palabras
    clave individuales en cualquier posicion del texto.

    Parametros
    ----------
    text : Input del usuario, ya sin espacios iniciales/finales.

    Devuelve
    --------
    True si el texto parece una solicitud de quiz.
    """
    normalized = text.lower().strip().rstrip("?.,!")
    for phrase in _QUIZ_PHRASES:
        if phrase in normalized:
            return True
    words = {w.rstrip("?.,!") for w in normalized.split()}
    return bool(words & _QUIZ_WORDS)


# ── Detección de modo review ──────────────────────────────────────────────────

_REVIEW_WORDS = {
    "repasar", "repaso", "revisar", "revision", "revisión",
    "review", "repasar",
}

_REVIEW_PHRASES = [
    "que debo repasar", "qué debo repasar",
    "que repasar", "qué repasar",
    "que estudiar", "qué estudiar",
    "sesion de repaso", "sesión de repaso",
    "modo repaso", "empezar repaso",
    "iniciar repaso",
]


def _is_review(text: str) -> bool:
    """
    Determina si el input solicita una sesión de repaso.

    Busca primero frases completas (mayor precisión) y luego palabras
    clave individuales en cualquier posición del texto.

    Parámetros
    ----------
    text : Input del usuario, ya sin espacios iniciales/finales.

    Devuelve
    --------
    True si el texto parece una solicitud de repaso.
    """
    normalized = text.lower().strip().rstrip("?.,!")
    for phrase in _REVIEW_PHRASES:
        if phrase in normalized:
            return True
    words = {w.rstrip("?.,!") for w in normalized.split()}
    return bool(words & _REVIEW_WORDS)


# ── Detección de modo question ────────────────────────────────────────────────

_QUESTION_STARTERS = {
    "que", "qué", "como", "cómo", "cual", "cuál", "cuales", "cuáles",
    "cuando", "cuándo", "donde", "dónde", "por", "quien", "quién",
    "explain", "define", "what", "how", "why", "when", "where", "who",
    # Verbos imperativos interrogativos que inician frases-pregunta
    "explicame", "dime", "cuentame",
}

# Frases de más de 4 palabras que empiezan con expresiones de pregunta implícita.
# Se usan en _is_question para inputs que _is_chat dejó pasar (len > 4 o > 6 palabras).
_QUESTION_PHRASE_STARTERS: list[str] = [
    "no entiendo que es",
    "no entiendo como",
    "no entiendo",
    "no se como",
    "no se que",
    "no se",
    "como funciona",
    "que es",
    "explicame",
    "cual es la diferencia",
    "cuales son",
    "para que sirve",
    "por que",
]

# Verbos de acción que raramente aparecen en términos técnicos compuestos pero
# son frecuentes en preguntas/oraciones (heurística para inputs > 6 palabras).
_SENTENCE_VERBS: set[str] = {
    "funciona", "sirve", "utiliza", "usa",
    "entiendo", "entiende", "entienden",
    "puede", "puedes",
    "quiero", "quieres",
    "explica", "explicar",
    "calcula", "calcular",
    "diferencia", "diferencias",
}


def _is_question(text: str) -> bool:
    """
    Determina si el input es una pregunta en lugar de un término nuevo.

    Orden de evaluación
    -------------------
    1. Si contiene '?' → pregunta.
    2. Si la primera palabra (normalizada) está en _QUESTION_STARTERS → pregunta.
    3. Si tiene más de 4 palabras y empieza con una frase de pregunta implícita
       (_QUESTION_PHRASE_STARTERS) → pregunta.  Captura casos como:
       'no entiendo qué es el machine learning', 'explícame el algoritmo SM-2'.
    4. Si tiene más de 6 palabras y contiene verbos de oración (_SENTENCE_VERBS)
       o empieza con una palabra no-técnica → probablemente una frase, no un término.

    Parámetros
    ----------
    text : Input del usuario, ya sin espacios iniciales/finales.

    Devuelve
    --------
    True si el input parece una pregunta o frase conversacional extensa.
    """
    if "?" in text:
        return True

    norm = _normalize(text)
    words = norm.split()

    if not words:
        return False

    # Regla 1: primera palabra interrogativa
    if words[0] in _QUESTION_STARTERS:
        return True

    # Regla 2: frase > 4 palabras que empieza con expresión de pregunta implícita
    if len(words) > 4:
        for phrase in _QUESTION_PHRASE_STARTERS:
            if norm.startswith(phrase):
                return True

    # Regla 3: input > 6 palabras con señales de oración (no término técnico compuesto)
    if len(words) > 6:
        if set(words) & _SENTENCE_VERBS:
            return True
        # Empieza con pronombres/negaciones que no inician términos técnicos
        if words[0] in {"no", "me", "yo", "te", "se"}:
            return True

    return False


# ── Helpers LLM (Sprint 14) ───────────────────────────────────────────────────

def _call_gemini_json(prompt: str) -> dict:
    """
    Llama a Gemini con un prompt que debe devolver JSON puro.

    Usa el mismo modelo configurado en GEMINI_MODEL (default: gemini-2.0-flash).
    Elimina bloques de código markdown si el modelo los añade.

    Parámetros
    ----------
    prompt : Texto completo del prompt.

    Devuelve
    --------
    dict parseado desde la respuesta JSON del modelo.

    Lanza
    -----
    Exception si la llamada falla o el JSON es inválido (el llamador debe capturar).
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
    response = llm.invoke([HumanMessage(content=prompt)])
    text = response.content.strip()
    # Quitar bloques de código markdown que el modelo añade a veces
    if text.startswith("```"):
        text = "\n".join(
            line for line in text.splitlines()
            if not line.startswith("```")
        ).strip()
    return json.loads(text)


# Herramientas y frameworks técnicos que nunca son ambiguos: se resuelven
# localmente sin llamar a Gemini.  Comparación case-insensitive.
_KNOWN_TECH_TOOLS: frozenset[str] = frozenset({
    # Editores e IDEs
    "cursor", "vs code", "vscode", "replit",
    # Control de versiones y colaboración
    "github", "gitlab", "linear", "notion", "slack",
    # Plataformas cloud / infraestructura
    "docker", "kubernetes", "terraform", "aws", "gcp", "azure",
    "supabase", "vercel",
    # Frameworks y librerías de IA / ML
    "langgraph", "langchain", "hugging face", "huggingface",
    # Modelos de IA y asistentes
    "gemini", "chatgpt", "claude", "perplexity", "antigravity", "openclaw",
    # Herramientas de diseño y API
    "figma", "postman",
    # Frameworks web / backend
    "streamlit", "react", "nextjs", "vue", "angular",
    "fastapi", "flask", "django",
    # Bases de datos
    "postgresql", "sqlite", "redis", "mongodb", "graphql",
    # Lenguajes de programación
    "python", "javascript", "typescript", "java", "rust", "go", "kotlin",
    "swift",
})


def _is_ambiguous(term: str, user_profile: dict | None = None) -> dict:
    """
    Detecta si el término tiene múltiples significados muy diferentes entre sí.

    Primero comprueba ``_KNOWN_TECH_TOOLS``: si el término coincide (sin
    distinguir mayúsculas) devuelve ``ambiguous=False`` directamente sin
    llamar a Gemini.  Esto evita la pregunta de clarificación para términos
    inequívocamente técnicos (Python, Cursor, Docker, etc.) y elimina el
    riesgo de loop de ambigüedad en reenvíos.

    Para el resto de términos llama a Gemini.  Si el perfil del usuario
    indica áreas técnicas/IA se añade una instrucción para que Gemini
    resuelva directamente cualquier término con significado técnico claro.

    Si la llamada a Gemini falla por cualquier razón devuelve no-ambiguo
    para no bloquear la captura.

    Parámetros
    ----------
    term         : Término introducido por el usuario.
    user_profile : Diccionario con claves ``profession``, ``learning_area``
                   y ``tech_level`` del usuario activo (puede ser None).

    Devuelve
    --------
    dict con claves:
        "ambiguous" (bool) — True si el término es ambiguo.
        "meanings"  (list[str]) — lista de 2-3 significados posibles.
    """
    # Shortcut: herramientas conocidas nunca son ambiguas
    if term.strip().lower() in _KNOWN_TECH_TOOLS:
        return {"ambiguous": False, "meanings": []}

    # Detectar perfil técnico/IA para reducir falsos positivos
    tech_areas = {"IA y tecnología", "Desarrollo de software"}
    learning_area_str = (user_profile or {}).get("learning_area", "")
    user_areas = {a.strip() for a in learning_area_str.split(",") if a.strip()}
    is_tech_profile = bool(user_areas & tech_areas)

    tech_hint = ""
    if is_tech_profile:
        tech_hint = (
            " El usuario tiene perfil técnico/IA. "
            "Si el término tiene un significado técnico claro en programación, "
            "infraestructura, IA o desarrollo de software, retorna "
            'ambiguous=false y usa ese significado directamente.'
        )

    prompt = (
        f'El término "{term}" ¿tiene múltiples significados muy diferentes entre sí '
        f"en tecnología y otros contextos?{tech_hint} "
        f'Responde SOLO con JSON válido: {{"ambiguous": true_o_false, '
        f'"meanings": ["significado 1", "significado 2"]}}'
    )
    try:
        result = _call_gemini_json(prompt)
        return {
            "ambiguous": bool(result.get("ambiguous", False)),
            "meanings": result.get("meanings", []),
        }
    except Exception:
        return {"ambiguous": False, "meanings": []}


def _check_spelling(term: str) -> dict:
    """
    Verifica si el término o frase (hasta 6 palabras) tiene un error ortográfico
    en contexto técnico/financiero.

    Detecta tanto errores clásicos ('piton' → 'Python') como errores de letras
    duplicadas o faltantes en términos técnicos conocidos ('COMIIT' → 'COMMIT').
    Llama a Gemini con un prompt de respuesta JSON.  Si la llamada falla por
    cualquier razón, devuelve sin-typo para no bloquear la captura.

    Parámetros
    ----------
    term : Término o frase introducida por el usuario.

    Devuelve
    --------
    dict con claves:
        "has_typo"  (bool) — True si parece haber un error ortográfico.
        "suggested" (str | None) — término correcto sugerido, o None.
    """
    prompt = (
        f'El término o frase "{term}" ¿parece tener un error ortográfico claro en el '
        f"contexto de finanzas, tecnología o negocios? "
        f"IMPORTANTE: NO marcar como error términos técnicos, nombres de herramientas, "
        f"frameworks, acrónimos, siglas ni palabras en inglés usadas habitualmente en "
        f"tecnología o finanzas (p. ej. EBITDA, Python, LangGraph, API, NFT, SaaS, "
        f"ROI, KPI, DataFrame, etc.). "
        f"Solo marcar errores ortográficos claros como 'ENITDA' en lugar de 'EBITDA' "
        f"o 'piton' en lugar de 'Python'. "
        f"También detecta errores de letras duplicadas o faltantes en términos técnicos "
        f"conocidos, por ejemplo: 'COMIIT' → 'COMMIT', 'MMERGE' → 'MERGE', "
        f"'DEPLOY' → 'DEPLOY', 'LANGGRAPH' → 'LANGGRAPH' (este último es correcto), "
        f"'COMIT' → 'COMMIT' (falta una T). Aplica solo si el error es evidente. "
        f'Responde SOLO con JSON válido: {{"has_typo": true_o_false, '
        f'"suggested": "término correcto, o null si no aplica"}}'
    )
    try:
        result = _call_gemini_json(prompt)
        suggested = result.get("suggested")
        # "null" como string o mismo término no es una sugerencia útil
        if not suggested or suggested in ("null", term):
            suggested = None
        return {
            "has_typo": bool(result.get("has_typo", False)),
            "suggested": suggested,
        }
    except Exception:
        return {"has_typo": False, "suggested": None}


# ── Nodo LangGraph ────────────────────────────────────────────────────────────

def capture_agent(state: NuraState) -> dict:
    """
    Nodo de captura: clasifica el input y persiste el concepto si es término nuevo.

    Comportamiento según tipo de input detectado
    --------------------------------------------
    Chat (mode='chat'):
        No toca la BD.  Respuesta conversacional breve del tutor sin LLM.

    Quiz (mode='quiz'):
        No toca la BD.  El grafo redirige a quiz_agent.

    Repaso (mode='review'):
        No toca la BD.  El grafo redirige a review_agent.

    Pregunta (mode='question'):
        No toca la BD.  El grafo redirige a tutor_agent.

    Término existente sin clasificar (mode='reclassify'):
        Detectado cuando get_concept_by_term devuelve un concepto con
        is_classified=False.  Se devuelve el concepto existente como
        current_concept para que classifier_agent lo enriquezca.

    Término nuevo (mode='capture'):
        1. Llama a save_concept(term, context, user_context).
        2. Llama a get_all_concepts() para el snapshot.
        3. Devuelve current_concept y all_concepts actualizados.

    Parámetros
    ----------
    state : Estado actual del grafo (NuraState).  Se lee user_context (Sprint 5).

    Devuelve
    --------
    dict parcial con los campos modificados.  LangGraph lo fusiona con el estado.

    Lanza
    -----
    ValueError : Si el término ya existe Y ya está clasificado.
    """
    user_input = state["user_input"].strip()
    raw_context = state.get("user_context", "")

    # Prefijos especiales que la UI adjunta según la acción del usuario.
    # [CLARIFIED]: → el usuario ya eligió un significado o forzó la captura;
    #               se omiten spelling y ambigüedad para evitar el loop.
    # [WEBSEARCH]: → el usuario pidió buscar en web; capture_agent activará
    #               mode='websearch_classify' y el nodo websearch_node hará
    #               la búsqueda antes de clasificar.
    _CLARIFIED_PREFIX = "[CLARIFIED]: "
    _WEBSEARCH_PREFIX  = "[WEBSEARCH]: "

    if raw_context.startswith(_CLARIFIED_PREFIX):
        user_context  = raw_context[len(_CLARIFIED_PREFIX):]
        bypass_checks = True
        do_websearch  = False
    elif raw_context.startswith(_WEBSEARCH_PREFIX):
        user_context  = raw_context[len(_WEBSEARCH_PREFIX):]
        bypass_checks = True
        do_websearch  = True
    else:
        user_context  = raw_context
        bypass_checks = False
        do_websearch  = False

    user_id: int = state.get("user_id", 1)  # Sprint 11: propagar user_id

    # Sprint 12 — prioridad -1: si el caller ya estableció mode='insight' en el estado
    # (invocado directamente desde la UI al inicio de sesión), pasar al insight_agent
    # sin tocar la BD ni ejecutar ninguna heurística de detección de modo.
    if state.get("mode") == "insight":
        return {
            "mode":            "insight",
            "current_concept": None,
            "quiz_questions":  [],
            "sources":         [],
            "response":        "",
            "insight_message": "",
        }

    # Prioridad 0: expresión conversacional — no toca la BD ni dispara LLM pesado
    if _is_chat(user_input):
        return {
            "mode": "chat",
            "current_concept": None,
            "quiz_questions": [],
            "sources": [],
            "response": "",
        }

    # Prioridad 1: quiz
    if _is_quiz(user_input):
        return {
            "mode": "quiz",
            "current_concept": None,
            "quiz_questions": [],
            "response": "",
        }

    # Prioridad 2: repaso
    if _is_review(user_input):
        return {
            "mode": "review",
            "current_concept": None,
            "quiz_questions": [],
            "response": "",
        }

    # Prioridad 3: pregunta
    if _is_question(user_input):
        return {
            "mode": "question",
            "current_concept": None,
            "quiz_questions": [],
            "response": "",
        }

    # Prioridad 3b: web search solicitado → delegar a websearch_node en el grafo
    # El nodo websearch_node llama a web_search, guarda el concepto con los
    # snippets como contexto y cambia mode a 'capture' para que el pipeline
    # continúe normalmente hacia classifier_agent.
    if do_websearch:
        return {
            "mode":                "websearch_classify",
            "current_concept":    None,
            "quiz_questions":     [],
            "sources":            [],
            "clarification_options": [],
            "spelling_suggestion":   "",
            "response":           "",
        }

    # Prioridad 4: verificar si el término existe en la BD
    existing = get_concept_by_term(user_input, user_id=user_id)
    if existing is not None:
        all_concepts = get_all_concepts(user_id=user_id)
        if not existing.is_classified:
            # Término sin clasificar → reclasificar directamente sin preguntar
            return {
                "mode": "reclassify",
                "current_concept": existing,
                "all_concepts": all_concepts,
                "new_connections": [],
                "response": f"Reintentando clasificar '{existing.term}'...",
                "clarification_options": [],
                "spelling_suggestion": "",
            }
        else:
            # Término ya clasificado → Sprint 20: preguntar al usuario si es el
            # mismo concepto o uno diferente, en lugar de reclasificar silenciosamente
            return {
                "mode": "confirm_reclassify",
                "current_concept": existing,
                "all_concepts": all_concepts,
                "new_connections": [],
                "response": (
                    f"Ya tengo '{existing.term}' en tu mapa — "
                    f"¿es el mismo concepto o uno diferente?"
                ),
                "clarification_options": [],
                "spelling_suggestion": "",
            }

    # Prioridad 4a: corrección ortográfica (Sprint 14)
    # Se activa para términos de hasta 6 palabras que no parecen frases largas.
    # Se omite cuando bypass_checks=True (término ya clarificado por el usuario).
    if not bypass_checks and len(user_input.split()) <= 6:
        spelling = _check_spelling(user_input)
        if spelling.get("has_typo") and spelling.get("suggested"):
            return {
                "mode": "spelling",
                "spelling_suggestion": spelling["suggested"],
                "clarification_options": [],
                "current_concept": None,
                "quiz_questions": [],
                "sources": [],
                "response": f"¿Quisiste decir '{spelling['suggested']}'?",
                "insight_message": "",
            }

    # Prioridad 4b: detección de ambigüedad (Sprint 14)
    # Solo se activa para términos cortos para evitar falsos positivos en frases.
    # Se omite cuando bypass_checks=True (término ya clarificado por el usuario).
    if not bypass_checks and len(user_input.split()) <= 4:
        ambig = _is_ambiguous(user_input, user_profile=state.get("user_profile"))
        if ambig.get("ambiguous") and ambig.get("meanings"):
            return {
                "mode": "clarify",
                "clarification_options": ambig["meanings"],
                "spelling_suggestion": "",
                "current_concept": None,
                "quiz_questions": [],
                "sources": [],
                "response": (
                    f"'{user_input}' puede significar varias cosas — ¿a cuál te refieres?"
                ),
                "insight_message": "",
            }

    # Prioridad 5: captura de término nuevo
    concept = save_concept(
        term=user_input,
        context="capturado por Nura",
        user_context=user_context,
        user_id=user_id,
    )
    all_concepts = get_all_concepts(user_id=user_id)

    return {
        "mode": "capture",
        "current_concept": concept,
        "all_concepts": all_concepts,
        "new_connections": [],
        "quiz_questions": [],
        "clarification_options": [],
        "spelling_suggestion": "",
        "response": f"Concepto '{concept.term}' capturado con id={concept.id}.",
    }


# ── Nodo websearch_classify ────────────────────────────────────────────────────

def websearch_node(state: NuraState) -> dict:
    """
    Nodo intermedio del pipeline mode='websearch_classify'.

    Flujo
    -----
    1. Llama a ``web_search(user_input)`` para obtener snippets actualizados.
    2. Guarda el concepto en la BD (o recupera el existente) con los snippets
       como ``user_context`` para que classifier_agent los use como contexto.
    3. Devuelve mode='capture' para que el grafo continúe normalmente hacia
       classifier_agent → connector_agent → END.

    El campo ``sources`` se rellena con los resultados crudos de la búsqueda
    para que la UI pueda mostrarlos bajo la respuesta del tutor.

    Parámetros
    ----------
    state : Estado actual del pipeline; se espera mode='websearch_classify'.

    Devuelve
    --------
    Diccionario parcial con los campos que este nodo modifica.
    """
    from tools.search_tool import web_search as _web_search

    user_input = state["user_input"].strip()
    user_id: int = state.get("user_id", 1)

    # ── Búsqueda web ──────────────────────────────────────────────────────────
    search_result = _web_search(user_input)
    sources = search_result.get("results", [])

    snippets = " | ".join(
        r.get("snippet", "") for r in sources[:3] if r.get("snippet")
    )
    web_context = f"[Búsqueda web] {snippets}" if snippets else ""

    # ── Guardar o recuperar concepto ─────────────────────────────────────────
    existing = get_concept_by_term(user_input, user_id=user_id)
    if existing is not None:
        concept = existing  # reclasificar con contexto web actualizado
    else:
        try:
            concept = save_concept(
                term=user_input,
                context="capturado por Nura vía web search",
                user_context=web_context,
                user_id=user_id,
            )
        except ValueError:
            # Pequeña carrera de escritura: el concepto fue creado entre el
            # get_concept_by_term de arriba y el save_concept.
            concept = get_concept_by_term(user_input, user_id=user_id)

    all_concepts = get_all_concepts(user_id=user_id)

    return {
        "mode":                  "capture",   # continúa hacia classifier
        "current_concept":       concept,
        "all_concepts":          all_concepts,
        "new_connections":       [],
        "sources":               sources,
        "user_context":          web_context,  # classifier_agent lo usará
        "clarification_options": [],
        "spelling_suggestion":   "",
        "response":              "",
    }
