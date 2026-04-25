# Sprint 27 — Audio / podcast por Telegram

## Objetivo
Nura genera audios con resúmenes y explicaciones
y los envía como notas de voz por Telegram.

## Funcionalidades

### 1. Audio del daily insight
- Comando `/podcast` → Nura genera un audio con
  tu resumen del día: cuánto aprendiste, qué conceptos
  nuevos tienes, qué debes repasar
- Duración objetivo: 60-90 segundos

### 2. Audio de explicación
- Comando `/audio [término]` → Nura explica el término
  en audio, adaptado a tu perfil
- Ejemplo: `/audio LangGraph`

### 3. Entrega
- El audio se envía como nota de voz en Telegram
  (sendVoice — formato OGG/OPUS que Telegram reproduce
  nativo sin descargar)

## Stack de TTS
- **Google Text-to-Speech (gTTS)** — gratuito, sin API key,
  genera MP3
- Convertir MP3 → OGG/OPUS con `pydub` + `ffmpeg`
- Idioma: español (es)

## Archivos a crear/modificar
- `bot/tts.py` — nuevo:
  `generate_audio(text) -> bytes` — genera OGG/OPUS
  `text_to_speech(text, lang='es') -> bytes`
- `bot/handlers.py` — nuevos comandos:
  `handle_podcast(user_id)` → genera insight en audio
  `handle_audio(user_id, term)` → explica término en audio
- `bot/main.py` — envío con `sendVoice` en lugar de
  `sendMessage` para respuestas de audio
- `requirements.txt` — agregar `gTTS`, `pydub`
- `Procfile` — agregar instalación de ffmpeg
- `tests/test_sprint27.py` — harness

## Harness
- `test_generate_audio_returns_bytes` — output es bytes
- `test_generate_audio_not_empty` — bytes no vacíos
- `test_podcast_command_detected` — `/podcast` →
  handle_podcast invocado
- `test_audio_command_with_term` — `/audio LangGraph` →
  handle_audio con término correcto
- `test_audio_command_no_term` — `/audio` sin término →
  mensaje de error amigable

## Reglas
- Si TTS falla → responder con texto en lugar de audio
  (nunca dejar al usuario sin respuesta)
- No tocar agentes ni tests existentes
- Correr pytest al cerrar y crear sprint27_close.md