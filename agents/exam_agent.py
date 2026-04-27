"""
agents/exam_agent.py
====================
Generación y evaluación de exámenes de certificación por categoría (Sprint 30).

Llama a Gemini para producir exactamente 10 preguntas de opción múltiple
(4 opciones), con dificultad progresiva: 3 fáciles, 4 medias, 3 difíciles.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.gemini_llm import GEMINI_REQUEST_TIMEOUT_SEC

load_dotenv(Path(__file__).parent.parent / ".env")

GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

EXAM_SYSTEM_PROMPT = (
    "Eres un diseñador de exámenes educativos. Genera EXACTAMENTE 10 preguntas "
    "de opción múltiple sobre los conceptos dados (categoría indicada por el usuario). "
    "Progresión obligatoria: preguntas 1-3 dificultad fácil, 4-7 media, 8-10 difícil. "
    "Cada pregunta: exactamente 4 opciones de texto; solo una correcta. "
    "El campo correct debe ser una sola letra minúscula: 'a', 'b', 'c' o 'd' "
    "(índice de la opción correcta en orden). "
    "Incluye en cada ítem el campo concept (término o idea principal evaluada) "
    "y difficulty: 'easy', 'medium' o 'hard' según la posición en la lista. "
    "Responde SOLO con JSON válido: una lista de 10 objetos con las claves: "
    "question (str), options (lista de 4 strings), correct ('a'|'b'|'c'|'d'), "
    "concept (str), difficulty ('easy'|'medium'|'hard'). "
    "Sin markdown ni texto fuera del JSON."
)


def _parse_json_list(raw: str) -> list[dict]:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        return []
    except (json.JSONDecodeError, ValueError):
        return []


def _normalize_correct(val: object) -> str | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in ("a", "b", "c", "d"):
        return s
    if s.isdigit():
        i = int(s)
        if 0 <= i <= 3:
            return "abcd"[i]
    return None


def _validate_exam_questions(items: list[dict]) -> list[dict]:
    """Devuelve exactamente 10 preguntas válidas o lista vacía."""
    valid: list[dict] = []
    for q in items:
        opts = q.get("options")
        if not isinstance(opts, list) or len(opts) != 4:
            continue
        if not all(isinstance(o, str) and str(o).strip() for o in opts):
            continue
        cor = _normalize_correct(q.get("correct"))
        if cor is None:
            continue
        question = str(q.get("question", "")).strip()
        if not question:
            continue
        concept = str(q.get("concept", "")).strip() or "—"
        diff = str(q.get("difficulty", "")).strip().lower()
        if diff not in ("easy", "medium", "hard"):
            diff = "medium"
        valid.append(
            {
                "question":   question,
                "options":    [str(o).strip() for o in opts],
                "correct":    cor,
                "concept":    concept,
                "difficulty": diff,
            }
        )
        if len(valid) == 10:
            break
    if len(valid) != 10:
        return []
    order = ["easy"] * 3 + ["medium"] * 4 + ["hard"] * 3
    for i, q in enumerate(valid):
        q["difficulty"] = order[i]
    return valid


def generate_exam(
    category: str,
    concepts: list[dict],
    user_profile: dict,
) -> list[dict]:
    """
    Genera 10 preguntas vía Gemini. Si falla el modelo o el parseo, retorna [].
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or not concepts:
        return []

    lines = [f'Categoría del examen: "{category}"']
    if user_profile:
        lines.append(f"Perfil del estudiante: {json.dumps(user_profile, ensure_ascii=False)}")
    lines.append("Conceptos (JSON):")
    lines.append(json.dumps(concepts[:40], ensure_ascii=False))
    human_text = "\n".join(lines)

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=api_key,  # type: ignore[call-arg]
        temperature=0.35,
        request_timeout=GEMINI_REQUEST_TIMEOUT_SEC,
    )
    messages = [
        SystemMessage(content=EXAM_SYSTEM_PROMPT),
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
                    for t in (
                        "403",
                        "PERMISSION_DENIED",
                        "API_KEY_INVALID",
                        "SERVICE_DISABLED",
                        "FORBIDDEN",
                    )
                ):
                    return []
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    if attempt < 2:
                        time.sleep(15 * (2**attempt))
                        continue
                return []
        else:
            return []
    except Exception:
        return []

    parsed = _parse_json_list(raw_response)
    return _validate_exam_questions(parsed)


def evaluate_exam(questions: list[dict], answers: list[str]) -> dict:
    """
    Compara respuestas con la clave `correct` de cada pregunta.

    Retorna score en [0,1], passed si score >= 0.8, conteos y feedback por ítem.
    """
    total = len(questions)
    if total == 0:
        return {
            "score":    0.0,
            "passed":   False,
            "correct":  0,
            "total":    0,
            "feedback": [],
        }
    correct_n = 0
    feedback: list[str] = []
    for i, q in enumerate(questions):
        want = str(q.get("correct", "")).strip().lower()
        got = ""
        if i < len(answers) and answers[i] is not None:
            got = str(answers[i]).strip().lower()
            if got and got[0] in "abcd":
                got = got[0]
        if got == want and want:
            correct_n += 1
            feedback.append("Correcto.")
        else:
            fb = f"Incorrecto. La respuesta correcta era {want.upper()}."
            concept = q.get("concept")
            if concept:
                fb += f" Concepto: {concept}."
            feedback.append(fb)
    score = correct_n / total
    return {
        "score":    score,
        "passed":   score >= 0.8,
        "correct":  correct_n,
        "total":    total,
        "feedback": feedback,
    }
