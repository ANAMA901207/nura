# Sprint 27 Close — Audio / podcast por Telegram

## Resultado del harness

```
6 passed, 0 failed, 0 regressions
32 passed total (sprints 23–27)
```

## Archivos modificados

| Archivo | Cambio |
|---|---|
| `requirements.txt` | Añadidos `gTTS==2.5.1` (TTS sin API key) y `pydub==0.25.1` (conversión MP3→OGG/OPUS) |
| `bot/tts.py` | **Nuevo archivo.** `text_to_speech(text, lang) -> bytes` (lazy import de gTTS+pydub), `generate_podcast_text(user_id) -> str` (guión diario personalizado), `generate_audio_explanation(user_id, term) -> str` (explicación breve via tutor) |
| `bot/handlers.py` | Añadidos `handle_podcast(telegram_id, user_id) -> dict` y `handle_audio(telegram_id, user_id, term) -> dict`; ambos retornan `{type: 'voice', audio_bytes}` en éxito y `{type: 'text'}` en fallback. Rutas `/podcast` y `/audio` en `process_update` |
| `bot/main.py` | `_process_and_send` actualizado para despachar a `_send_voice` cuando `result["type"] == "voice"`; añadida `_send_voice(token, chat_id, audio_bytes)` que usa `sendVoice` con multipart/form-data |
| `tests/test_sprint27.py` | **Nuevo archivo.** 6 casos con stub de pydub en `sys.modules` para Python 3.14 (audioop removido) |

## Decisiones de diseño

### Lazy import de gTTS y pydub
pydub 0.25.1 importa `audioop` a nivel de módulo, que fue eliminado en Python 3.13/3.14.
Para que `bot/tts.py` sea importable en el entorno de desarrollo (Python 3.14) sin errores:
- Los imports de `gTTS` y `AudioSegment` se mueven dentro de `text_to_speech`.
- Solo falla cuando la función se llama (fallback a texto garantiza que el usuario siempre recibe respuesta).
- En Railway (Python 3.11/3.12 con nixpacks + `ffmpeg`), pydub funciona sin problemas.

### Stub de pydub en sys.modules (tests)
Para los tests en Python 3.14, se inyecta un `MagicMock` como stub de pydub en `sys.modules`
antes de que cualquier import lo intente. Esto permite:
- Importar `bot.tts` sin errores.
- Usar `patch.dict(sys.modules, ...)` en `test_tts_returns_bytes` para controlar `AudioSegment.from_mp3` y `audio.export`.

### Handlers retornan dicts completos para voz
A diferencia de los handlers de texto (que retornan `str` y `process_update` los envuelve),
`handle_podcast` y `handle_audio` retornan el dict completo `{chat_id, type, audio_bytes/text, handled}`.
Esto permite que `process_update` retorne directamente (`return await handle_podcast(...)`)
y que `_process_and_send` despache a `_send_voice` o `_send_message` según `result["type"]`.

### Fallback garantizado
Si TTS falla (sin red, sin ffmpeg, `audioop` ausente), el handler captura la excepción
y retorna la versión en texto. El usuario siempre recibe una respuesta.

## Notas de despliegue

- `nixpacks.toml` ya tenía `ffmpeg` como dependencia — sin cambios necesarios.
- En Railway, pydub encontrará `ffmpeg` en PATH y la conversión MP3→OGG funcionará.
- `requirements.txt` actualizado con versiones exactas de gTTS y pydub.

## Estado del proyecto

- **Bot de Telegram** (Sprints 25–27): webhook async, comandos, scheduler de alertas y ahora audio.
- **Comandos activos**: `/start`, `/capturar`, `/repasar`, `/streak`, `/meta`, `/vincular`, `/recordatorio`, `/podcast`, `/audio`.
- **Suite de tests**: 32 passed (sprints 23–27), 0 regressions.
