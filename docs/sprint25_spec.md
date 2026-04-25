# Sprint 25 — Bot de Telegram

## Objetivo
Crear un bot de Telegram que sea una interfaz completa
de Nura — el usuario puede conversar, capturar conceptos
y consultar su progreso desde Telegram.

## Arquitectura
- Bot independiente en `bot/` con FastAPI + python-telegram-bot
- Se conecta a la misma Supabase que la app
- Telegram envía mensajes via webhook a FastAPI
- FastAPI los procesa usando los mismos agentes de Nura

## Comandos
- `/start` — saludo, menú de opciones
- `/capturar [término]` — captura un concepto nuevo
- `/repasar` — lista conceptos pendientes según SM-2
- `/streak` — muestra racha actual y progreso del día
- `/meta [número]` — cambia meta diaria
- Mensaje libre → tutor responde con contexto completo

## Archivos a crear
- `bot/main.py` — FastAPI app + webhook handler
- `bot/handlers.py` — lógica de cada comando
- `bot/nura_bridge.py` — conecta handlers con agentes
  y operaciones de BD existentes
- `bot/requirements.txt` — dependencias del bot
- `Procfile` — para Railway
- `tests/test_sprint25.py` — harness

## Comportamiento esperado
- Usuario escribe `/start` → Nura se presenta y muestra menú
- Usuario escribe un término → Nura lo captura y confirma
- Usuario hace una pregunta → tutor responde con su contexto
- Usuario escribe `/streak` → ve su racha y progreso
- Toda la data se sincroniza con Supabase en tiempo real

## Vinculación de usuario
- Primera vez → bot pide un código de vinculación
- El usuario genera ese código desde la app Streamlit
- El código vincula su telegram_id con su user_id en Supabase
- Sin vinculación → bot no responde funcionalidades

## Harness
- `test_start_command_returns_welcome` 
- `test_free_message_routes_to_tutor`
- `test_capturar_command_saves_concept`
- `test_streak_command_returns_data`
- `test_unlinked_user_gets_prompt`
- `test_nura_bridge_connects_to_db`

## Reglas
- No tocar nada de `ui/`, `agents/` ni tests existentes
- El bot es un módulo nuevo — no modifica Nura, la extiende
- Correr pytest al cerrar y crear sprint25_close.md