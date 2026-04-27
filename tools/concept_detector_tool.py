"""
tools/concept_detector_tool.py
================================
Detecta conceptos técnicos o de negocio nuevos en el texto de respuesta
del tutor que el usuario aún no tiene en su mapa de conocimiento.

Flujo de uso (Sprint 18)
------------------------
1. detect_new_concepts(response_text, existing_terms, user_id) — llama a
   Gemini para extraer sustantivos técnicos del texto, filtra los que ya
   existen en el mapa del usuario y devuelve hasta 5 sugerencias.

Comportamiento ante fallos
--------------------------
Si la llamada a Gemini falla por cualquier motivo (cuota, timeout, clave
inválida) la función retorna una lista vacía sin propagar la excepción.
"""

from __future__ import annotations

import json
import os
import re


def _call_gemini_concepts(prompt: str) -> dict:
    """
    Llama a Gemini esperando una respuesta JSON con la clave 'concepts'.

    Elimina bloques markdown del output antes de parsear el JSON.

    Parámetros
    ----------
    prompt : Prompt completo a enviar al modelo.

    Devuelve
    --------
    dict con la respuesta parseada.

    Lanza
    -----
    Exception si la llamada falla o si el JSON es inválido.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    from agents.gemini_llm import GEMINI_REQUEST_TIMEOUT_SEC

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    api_key    = os.environ.get("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,  # type: ignore[call-arg]
        temperature=0,
        request_timeout=GEMINI_REQUEST_TIMEOUT_SEC,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    text = str(response.content).strip()
    # Eliminar bloques ```json ... ```
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(text)


def detect_new_concepts(
    response_text: str,
    existing_terms: list[str],
    user_id: int = 1,  # noqa: ARG001 — reservado para personalización futura
) -> list[str]:
    """
    Extrae conceptos técnicos nuevos del texto de respuesta del tutor.

    El proceso tiene tres etapas:
    1. Llama a Gemini para identificar sustantivos técnicos en el texto.
    2. Filtra los que ya existen en el mapa de conocimiento del usuario
       (comparación case-insensitive).
    3. Devuelve como máximo 5 conceptos, ordenados tal como Gemini los
       devolvió (los más relevantes primero).

    Si el texto es demasiado corto o la llamada a Gemini falla, devuelve
    una lista vacía sin propagar ninguna excepción.

    Parámetros
    ----------
    response_text   : Texto de la respuesta del tutor a analizar.
    existing_terms  : Lista de términos que el usuario ya tiene capturados
                      en su mapa (comparación case-insensitive).
    user_id         : ID del usuario autenticado.  Actualmente no se usa
                      en la lógica interna pero se incluye por consistencia
                      con el resto de herramientas del proyecto.

    Devuelve
    --------
    list[str] con hasta 5 conceptos técnicos nuevos, o lista vacía.
    """
    if not response_text or len(response_text.strip()) < 20:
        return []

    # Usar solo las primeras 800 chars para mantener el prompt compacto
    snippet = response_text.strip()[:800]
    prompt = (
        f'Del siguiente texto extrae SOLO términos técnicos específicos — '
        f'herramientas, frameworks, algoritmos, métricas financieras, metodologías, '
        f'tecnologías. '
        f'NO incluir: palabras genéricas, frases descriptivas, conceptos abstractos '
        f'como maestría, conocimiento, nivel, base, mapa, concepto, aprendizaje. '
        f'Ejemplos válidos: LangGraph, EBITDA, Docker, regresión logística, webhook. '
        f'Ejemplos inválidos: base de conocimiento, nivel de maestría, conceptos clave. '
        f'Responde SOLO con JSON: {{"concepts": [lista máximo 5 términos técnicos específicos]}}. '
        f'Texto: "{snippet}"'
    )
    try:
        data = _call_gemini_concepts(prompt)
        raw: list = data.get("concepts") or []
        if not isinstance(raw, list):
            return []

        # Normalizar para comparar case-insensitive
        existing_lower = {t.lower() for t in existing_terms}

        # Filtrar los que el usuario ya tiene y limpiar strings
        filtered: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            clean = item.strip()
            if not clean:
                continue
            # Respetar el límite de 4 palabras
            if len(clean.split()) > 4:
                continue
            # Excluir si ya existe (case-insensitive)
            if clean.lower() in existing_lower:
                continue
            filtered.append(clean)
            if len(filtered) >= 5:
                break

        return filtered
    except Exception:
        return []
