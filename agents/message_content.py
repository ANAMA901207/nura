"""
agents/message_content.py
===========================
Normaliza el campo ``content`` de mensajes LangChain (AIMessage, etc.)
a texto plano para persistir en ``NuraState.response`` y enviar al usuario.

Gemini vía LangChain puede devolver ``content`` como str, lista de bloques
``{"type": "text", "text": "..."}``, o un solo dict con ``type``/``text``.
"""

from __future__ import annotations


def message_content_to_str(content: object) -> str:
    """
    Convierte ``content`` de un AIMessage (o similar) en un único string.

    Si no hay texto reconocible, devuelve cadena vacía.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                s = block.strip()
                if s:
                    parts.append(s)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    t = block.get("text")
                    if isinstance(t, str) and t:
                        parts.append(t)
                else:
                    t = block.get("text") or block.get("content", "")
                    if isinstance(t, str) and t:
                        parts.append(t)
        return "".join(parts).strip()
    if isinstance(content, dict) and content.get("type") == "text":
        t = content.get("text", "")
        if isinstance(t, str):
            return t.strip()
    s = str(content).strip()
    return s if s and s not in ("None",) else ""
