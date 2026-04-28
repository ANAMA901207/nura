"""
bot/tts.py
==========
Text-to-Speech (TTS) y generación de contenido de audio para Nura.

Funciones principales
---------------------
text_to_speech(text, lang) -> bytes
    Convierte texto a OGG/OPUS (formato nativo de notas de voz de Telegram).
    Usa gTTS para generar MP3 en memoria y pydub + ffmpeg para convertirlo a OGG.

generate_podcast_text(user_id) -> str
    Construye el guión del resumen diario del usuario:
    saludo + progreso del día + conceptos pendientes + términos recientes.
    Máximo ~500 palabras.

generate_audio_explanation(user_id, term) -> str
    Invoca al tutor de Nura para obtener una explicación breve del término,
    limitada a ~300 palabras, lista para convertir a audio.

Manejo de errores
-----------------
Si text_to_speech falla (sin red, sin ffmpeg, gTTS devuelve error) lanza
una excepción con mensaje claro.  El caller (handler) decide el fallback.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# gTTS y pydub se importan dentro de text_to_speech para que:
# 1. El módulo sea importable sin errores aunque falten dependencias nativas
#    (pydub usa 'audioop' que fue removido en Python 3.13/3.14 — solo la
#    función que lo llama fallará, no todo el módulo).
# 2. En tests se puedan inyectar mocks vía sys.modules antes de llamar a la función.


def text_to_speech(text: str, lang: str = "es") -> bytes:
    """
    Convierte texto a audio OGG/OPUS listo para sendVoice en Telegram.

    Parámetros
    ----------
    text : Texto a convertir. No puede estar vacío.
    lang : Código de idioma gTTS (por defecto "es" para español).

    Devuelve
    --------
    bytes — contenido OGG/OPUS.

    Lanza
    -----
    ValueError       : Si text está vacío.
    RuntimeError     : Si gTTS o pydub/ffmpeg fallan, con mensaje descriptivo.
    """
    if not text.strip():
        raise ValueError("El texto para TTS no puede estar vacío.")

    # Importación lazy: solo falla si se llama la función, no al importar el módulo
    from gtts import gTTS                           # noqa: PLC0415
    from pydub import AudioSegment                  # noqa: PLC0415

    # Paso 1: generar MP3 en memoria con gTTS
    try:
        tts = gTTS(text=text, lang=lang)
        mp3_buf = io.BytesIO()
        tts.write_to_fp(mp3_buf)
        mp3_buf.seek(0)
    except Exception as exc:
        raise RuntimeError(f"gTTS no pudo generar el audio: {exc}") from exc

    # Paso 2: convertir MP3 → OGG/OPUS con pydub (requiere ffmpeg en PATH)
    try:
        audio = AudioSegment.from_mp3(mp3_buf)
        ogg_buf = io.BytesIO()
        audio.export(ogg_buf, format="ogg", codec="libopus")
        ogg_buf.seek(0)
        return ogg_buf.read()
    except Exception as exc:
        raise RuntimeError(
            f"pydub no pudo convertir el audio a OGG/OPUS: {exc}. "
            "Asegúrate de que ffmpeg esté instalado."
        ) from exc


def generate_podcast_text(user_id: int) -> str:
    """
    Genera el guión del podcast diario personalizado del usuario.

    Incluye:
      - Saludo
      - Conceptos capturados hoy vs. meta
      - Conceptos pendientes de repasar (SM-2)
      - Hasta 3 términos recientes mencionados por nombre
      - Frase de cierre motivacional

    Parámetros
    ----------
    user_id : ID del usuario en Nura.

    Devuelve
    --------
    str — texto de máximo ~500 palabras.
    """
    from db.operations import get_today_count, get_daily_goal, get_all_concepts
    from bot.nura_bridge import get_pending_concepts

    today_count   = get_today_count(user_id)
    daily_goal    = get_daily_goal(user_id)
    pending_list  = get_pending_concepts(user_id)
    pending       = len(pending_list)
    all_concepts  = get_all_concepts(user_id)

    def _concept_term_only(c: object) -> str:
        """Solo el campo `term` del concepto (nunca id, categoría ni __str__)."""
        raw = getattr(c, "term", None)
        if raw is None:
            return ""
        return str(raw).strip()

    def _concept_recency_key(c: object) -> tuple:
        ca = getattr(c, "created_at", None)
        if hasattr(ca, "timestamp"):
            try:
                ts = float(ca.timestamp())
            except (OSError, ValueError, TypeError):
                ts = 0.0
        else:
            ts = 0.0
        cid = int(getattr(c, "id", 0) or 0)
        return (ts, cid)

    sorted_concepts = sorted(all_concepts, key=_concept_recency_key, reverse=True)
    recent_terms: list[str] = []
    for c in sorted_concepts:
        t = _concept_term_only(c)
        if t and t not in recent_terms:
            recent_terms.append(t)
        if len(recent_terms) >= 3:
            break

    lines: list[str] = [
        "Hola, aquí está tu resumen de Nura para hoy.",
        f"Hoy llevas {today_count} de {daily_goal} concepto{'s' if daily_goal != 1 else ''} capturado{'s' if today_count != 1 else ''}.",
    ]

    if pending > 0:
        lines.append(
            f"Tienes {pending} concepto{'s' if pending != 1 else ''} "
            f"pendiente{'s' if pending != 1 else ''} de repasar."
        )
    else:
        lines.append("¡Estás al día con todos tus repasos!")

    if recent_terms:
        if len(recent_terms) == 1:
            lines.append(f"Tu concepto más reciente es: {recent_terms[0]}.")
        else:
            joined = ", ".join(recent_terms[:-1]) + f" y {recent_terms[-1]}"
            lines.append(f"Tus conceptos más recientes son: {joined}.")

    if today_count >= daily_goal:
        lines.append("¡Excelente! Ya cumpliste tu meta del día. Sigue así.")
    else:
        remaining = daily_goal - today_count
        lines.append(
            f"Te {'falta' if remaining == 1 else 'faltan'} {remaining} "
            f"concepto{'s' if remaining != 1 else ''} para cumplir la meta de hoy. ¡Tú puedes!"
        )

    text = " ".join(lines)

    # Limitar a ~500 palabras
    words = text.split()
    if len(words) > 500:
        text = " ".join(words[:500]) + "."

    return text


def generate_audio_explanation(user_id: int, term: str) -> str:
    """
    Genera una explicación breve del término invocando al tutor de Nura.

    Parámetros
    ----------
    user_id : ID del usuario en Nura (para contexto del tutor).
    term    : Término a explicar.

    Devuelve
    --------
    str — explicación de máximo ~300 palabras, lista para TTS.
    """
    from bot.nura_bridge import run_tutor

    prompt = (
        f"Explícame brevemente el concepto '{term}' en 2 o 3 oraciones "
        "claras y sencillas, como si se lo explicaras a alguien en un podcast."
    )
    text = run_tutor(user_id, prompt)

    # Limitar a ~300 palabras
    words = text.split()
    if len(words) > 300:
        text = " ".join(words[:300]) + "."

    return text
