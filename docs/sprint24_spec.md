# Sprint 24 — Streak y meta diaria

## Objetivo
Crear hábito de uso diario con un streak visible y una
meta de conceptos por día configurable por el usuario.

## Funcionalidades

### 1. Streak
- Contador de días consecutivos en que el usuario capturó
  al menos 1 concepto
- Se muestra en la UI de forma prominente
- Si el usuario no captura nada en un día, el streak
  vuelve a 0
- El streak se calcula desde la BD — no desde session_state

### 2. Meta diaria
- El usuario configura cuántos conceptos quiere capturar
  por día (default: 3)
- Una barra de progreso muestra cuántos lleva hoy vs su meta
- Cuando completa la meta → toast motivacional
- La meta se guarda en el perfil del usuario en BD

## Archivos a modificar
- `db/schema.py` — campo `daily_goal INT DEFAULT 3`
  en tabla users
- `db/operations.py` — funciones:
  `get_streak(user_id)` → int
  `get_today_count(user_id)` → int
  `update_daily_goal(user_id, goal)` → None
  `get_daily_goal(user_id)` → int
- `ui/app.py` — mostrar streak y barra de progreso
  en vista Descubrir
- `ui/components.py` — `render_streak(streak, today, goal)`

## Comportamiento esperado
- Streak visible apenas el usuario entra a Descubrir
- Barra de progreso se actualiza cada vez que captura
  un concepto
- Al completar meta → toast "¡Meta del día cumplida! 🔥"
- En perfil → input para cambiar meta diaria

## Harness
- `test_streak_zero_new_user` — usuario sin conceptos → 0
- `test_streak_one_day` — conceptos solo hoy → 1
- `test_streak_consecutive_days` — conceptos 3 días
  seguidos → 3
- `test_streak_broken` — gap de un día → streak reinicia
- `test_today_count` — cuenta correcta de conceptos de hoy
- `test_daily_goal_default` — nuevo usuario → goal = 3
- `test_update_daily_goal` — cambiar goal persiste en BD

## Reglas
- No tocar agentes
- Preservar todos los tests existentes en verde
- Correr pytest al cerrar y crear sprint24_close.md