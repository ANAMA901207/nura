"""
agents/hierarchy_agent.py
=========================
Agente que detecta relaciones jerárquicas entre un concepto recién capturado
y los conceptos existentes del usuario.

Función principal
-----------------
detect_hierarchy(new_concept, existing_concepts, user_profile) -> list[dict]

    Llama a Gemini con un prompt que analiza el nuevo concepto en el contexto
    de los existentes y devuelve JSON con las relaciones detectadas.

    Si Gemini falla o no detecta relaciones → retorna lista vacía.
    NUNCA lanza excepciones al caller: la captura no debe bloquearse.

Tipos de relación soportados
-----------------------------
- "es_tipo_de"  : el nuevo concepto es un subtipo/caso especial del padre.
                  Ejemplo: "Machine Learning" es_tipo_de "Inteligencia Artificial"
- "contiene"    : el nuevo concepto contiene/agrupa a los hijos.
                  Ejemplo: "Inteligencia Artificial" contiene "Machine Learning"
- "es_parte_de" : el nuevo concepto es un componente del padre.
                  Ejemplo: "Transformers" es_parte_de "Deep Learning"
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_VALID_RELATIONS = {"es_tipo_de", "contiene", "es_parte_de"}
_MAX_EXISTING = 20   # máximo de conceptos existentes que se pasan a Gemini


def detect_hierarchy(
    new_concept: dict,
    existing_concepts: list[dict],
    user_profile: dict,
) -> list[dict]:
    """
    Detecta relaciones jerárquicas entre el nuevo concepto y los existentes.

    Parámetros
    ----------
    new_concept       : dict con al menos "id", "term" y opcionalmente
                        "category", "subcategory", "explanation".
    existing_concepts : lista de dicts con los mismos campos que new_concept.
                        Se usan los últimos _MAX_EXISTING (más recientes).
    user_profile      : dict con "profession", "learning_area", "tech_level"
                        del usuario (para contextualizar el prompt).

    Devuelve
    --------
    list[dict] — cada elemento tiene:
        {
          "child_id":      int,   # ID del concepto hijo
          "parent_id":     int,   # ID del concepto padre
          "relation_type": str,   # "es_tipo_de" | "contiene" | "es_parte_de"
        }
    Lista vacía si no se detectan relaciones o si Gemini falla.
    """
    if not existing_concepts:
        return []

    # Limitar la ventana de conceptos existentes
    candidates = existing_concepts[-_MAX_EXISTING:]
    # Excluir el concepto nuevo si por alguna razón está en la lista
    candidates = [c for c in candidates if c.get("id") != new_concept.get("id")]
    if not candidates:
        return []

    new_id   = new_concept.get("id")
    new_term = new_concept.get("term", "")

    # Serializar los candidatos de forma concisa para el prompt
    candidates_txt = "\n".join(
        f'  - id={c.get("id")}, term="{c.get("term", "")}", '
        f'category="{c.get("category", "")}"'
        for c in candidates
    )

    area = (user_profile or {}).get("learning_area", "general")

    prompt = f"""Eres un experto en organización del conocimiento en el área de {area}.

Nuevo concepto capturado:
  id={new_id}, term="{new_term}", category="{new_concept.get('category', '')}"

Conceptos existentes del usuario:
{candidates_txt}

Analiza si existe una relación jerárquica entre el nuevo concepto y alguno de los existentes.
Tipos de relación posibles:
  - "es_tipo_de":  el concepto A es un subtipo o caso especial del concepto B
  - "contiene":    el concepto A agrupa o engloba al concepto B
  - "es_parte_de": el concepto A es un componente o parte del concepto B

Reglas:
1. Solo reporta relaciones que sean claramente correctas desde el punto de vista conceptual.
2. Para cada relación, especifica child_id (el más específico) y parent_id (el más general).
3. Si no hay relaciones claras, devuelve lista vacía.
4. Máximo 3 relaciones.

Responde SOLO con JSON válido, sin explicaciones ni bloques de código markdown:
[
  {{"child_id": <int>, "parent_id": <int>, "relation_type": "<es_tipo_de|contiene|es_parte_de>"}},
  ...
]
Si no hay relaciones: []"""

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage

        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()

        # Quitar bloques de código markdown si el modelo los añade
        if raw.startswith("```"):
            raw = "\n".join(
                line for line in raw.splitlines()
                if not line.startswith("```")
            ).strip()

        parsed = json.loads(raw)

        if not isinstance(parsed, list):
            return []

        # Validar y filtrar cada relación
        valid: list[dict] = []
        all_ids = {c.get("id") for c in candidates} | {new_id}
        for rel in parsed:
            child_id      = rel.get("child_id")
            parent_id     = rel.get("parent_id")
            relation_type = rel.get("relation_type", "")

            if (
                isinstance(child_id, int)
                and isinstance(parent_id, int)
                and child_id != parent_id
                and child_id in all_ids
                and parent_id in all_ids
                and relation_type in _VALID_RELATIONS
            ):
                valid.append({
                    "child_id":      child_id,
                    "parent_id":     parent_id,
                    "relation_type": relation_type,
                })

        return valid[:3]

    except Exception:
        return []
