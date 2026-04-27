"""
agents/quiz_agent.py
====================
Nodo LangGraph que genera un quiz de opciones multiples sobre los conceptos
del usuario.

Se activa cuando capture_agent detecta mode='quiz' (el usuario escribe algo
como 'quiz', 'ponme a prueba', 'hazme un examen').  Selecciona hasta 5
conceptos clasificados de la BD al azar, llama a Gemini para generar
preguntas de opcion multiple y guarda el resultado en state.quiz_questions
para que la UI las consuma.

No persiste nada en la BD.  El resultado del quiz (correcto/incorrecto)
se registra en la UI via record_flashcard_result cuando el usuario
completa el quiz.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from db.operations import get_all_concepts
from agents.gemini_llm import GEMINI_REQUEST_TIMEOUT_SEC
from agents.state import NuraState

load_dotenv(Path(__file__).parent.parent / ".env")

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# Numero maximo de conceptos que se incluyen en un quiz
MAX_QUIZ_CONCEPTS = 5

QUIZ_SYSTEM_PROMPT = (
    "Genera un quiz de opcion multiple sobre los conceptos dados. "
    "Para cada concepto genera UNA pregunta con exactamente 4 opciones "
    "donde solo una es correcta. "
    "Responde SOLO con JSON valido: una lista de objetos con los campos: "
    "concept_id (int), "
    "question (str), "
    "options (lista de exactamente 4 strings), "
    "correct_index (int entre 0 y 3 inclusive), "
    "explanation (str — por que esa opcion es correcta). "
    "Sin texto adicional antes ni despues. Solo JSON."
)


def _parse_quiz_json(raw: str) -> list[dict]:
    """
    Extrae y parsea el JSON de la respuesta del LLM.

    Elimina los bloques de codigo markdown (```json ... ```) que Gemini
    puede incluir aunque se le pida JSON puro, y luego parsea el resultado.

    Parametros
    ----------
    raw : String crudo devuelto por el LLM.

    Devuelve
    --------
    list[dict] con las preguntas del quiz, o lista vacia si no se puede parsear.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, ValueError):
        return []


def _validate_questions(questions: list[dict]) -> list[dict]:
    """
    Filtra preguntas malformadas para asegurar que la UI no falle.

    Requisitos por pregunta:
    - Debe tener los campos: concept_id, question, options, correct_index, explanation.
    - options debe ser una lista de exactamente 4 elementos.
    - correct_index debe ser un entero entre 0 y 3 inclusive.

    Parametros
    ----------
    questions : Lista de dicts devuelta por el LLM.

    Devuelve
    --------
    Lista filtrada con solo las preguntas validas.
    """
    valid = []
    required = {"concept_id", "question", "options", "correct_index", "explanation"}
    for q in questions:
        if not isinstance(q, dict):
            continue
        if not required.issubset(q.keys()):
            continue
        opts = q.get("options", [])
        if not isinstance(opts, list) or len(opts) != 4:
            continue
        ci = q.get("correct_index", -1)
        if not isinstance(ci, int) or not (0 <= ci <= 3):
            continue
        valid.append(q)
    return valid


def quiz_agent(state: NuraState) -> dict:
    """
    Nodo quiz: genera preguntas de opcion multiple para los conceptos del usuario.

    Flujo interno
    -------------
    1. Carga todos los conceptos clasificados desde la BD.
    2. Si hay menos de 1 concepto clasificado, devuelve mensaje amigable.
    3. Selecciona aleatoriamente hasta MAX_QUIZ_CONCEPTS conceptos.
    4. Construye el prompt con los conceptos seleccionados (id, termino, explicacion).
    5. Llama a Gemini con retry para rate limits transitorios.
    6. Parsea y valida el JSON de preguntas.
    7. Devuelve las preguntas en state.quiz_questions.

    El agente NO persiste nada en la BD.  Los resultados del quiz se
    registran en la UI via record_flashcard_result.

    Parametros
    ----------
    state : Estado actual del grafo.  No se usa ningun campo del input.

    Devuelve
    --------
    dict parcial con quiz_questions y response actualizados.

    Lanza
    -----
    EnvironmentError : Si GOOGLE_API_KEY no esta definida.
    RuntimeError     : Si Gemini falla despues de 3 reintentos.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return {
            "quiz_questions": [],
            "response": (
                "GOOGLE_API_KEY no está configurada. "
                "Agrega tu clave al archivo .env en la raíz del proyecto."
            ),
        }

    user_id: int = state.get("user_id", 1)  # Sprint 11
    all_concepts = get_all_concepts(user_id=user_id)
    classified = [c for c in all_concepts if c.is_classified and c.flashcard_front]

    if not classified:
        return {
            "quiz_questions": [],
            "response": (
                "No hay conceptos clasificados para generar un quiz. "
                "Captura y clasifica algunos terminos primero."
            ),
        }

    selected = random.sample(classified, min(MAX_QUIZ_CONCEPTS, len(classified)))

    # Construye el contexto de conceptos para el prompt
    concept_lines = []
    for c in selected:
        line = f'- id={c.id}, termino="{c.term}"'
        if c.explanation:
            line += f', explicacion="{c.explanation[:200]}"'
        if c.category:
            line += f', categoria="{c.category}"'
        concept_lines.append(line)

    human_text = "Conceptos:\n" + "\n".join(concept_lines)

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=api_key,  # type: ignore[call-arg]
        temperature=0.4,
        request_timeout=GEMINI_REQUEST_TIMEOUT_SEC,
    )

    messages = [
        SystemMessage(content=QUIZ_SYSTEM_PROMPT),
        HumanMessage(content=human_text),
    ]

    raw_response = ""
    try:
        for attempt in range(3):
            try:
                response = llm.invoke(messages)
                raw_response = str(response.content).strip()
                break
            except Exception as exc:
                err = str(exc).upper()
                if any(
                    t in err
                    for t in ("403", "PERMISSION_DENIED", "API_KEY_INVALID",
                              "SERVICE_DISABLED", "FORBIDDEN", "INVALID API KEY")
                ):
                    return {
                        "quiz_questions": [],
                        "response": (
                            "No puedo conectarme al servicio de IA. "
                            "Verifica que GOOGLE_API_KEY en el archivo .env sea válida "
                            "y que la API de Gemini esté habilitada. "
                            "(Error 403 / PERMISSION_DENIED)"
                        ),
                    }
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    if attempt < 2:
                        time.sleep(15 * (2 ** attempt))
                        continue
                return {
                    "quiz_questions": [],
                    "response": f"No pude generar el quiz ahora: {str(exc)[:200]}",
                }
        else:
            return {
                "quiz_questions": [],
                "response": (
                    "El servicio de IA está saturado ahora mismo. "
                    "Espera unos minutos y vuelve a intentarlo. 🌙"
                ),
            }
    except Exception as exc:
        return {
            "quiz_questions": [],
            "response": f"No pude generar el quiz ahora: {str(exc)[:200]}",
        }

    questions = _parse_quiz_json(raw_response)
    questions = _validate_questions(questions)

    n = len(questions)
    response_msg = (
        f"Quiz generado con {n} pregunta(s) sobre: "
        + ", ".join(c.term for c in selected[:n])
        + ". Responde en el panel de abajo."
        if n > 0
        else "No se pudieron generar preguntas validas. Intenta de nuevo."
    )

    return {
        "quiz_questions": questions,
        "response": response_msg,
    }
