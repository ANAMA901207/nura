# Sprint 8 — SM-2 Spaced Repetition (Cerrado)

## Resultado: 5/5 tests pasados

## Qué se construyó

### db/models.py
- Nuevos campos en `Concept`:
  - `sm2_interval: float = 1.0` — días hasta el próximo repaso
  - `sm2_ef: float = 2.5` — Easiness Factor del algoritmo SM-2 (mínimo 1.3)

### db/schema.py
- `_SPRINT8_MIGRATIONS` con columnas `sm2_interval REAL` y `sm2_ef REAL`
- Integradas en `_run_migrations()` junto a las migraciones anteriores

### db/operations.py
- `record_flashcard_result` reemplazado con implementación SM-2 completa:
  - **Acierto (q=4)**: `new_ef = ef + (0.1 - 1*(0.08 + 1*0.02))` → sin cambio de EF con q=4; intervalo: 1er acierto→1d, 2º→6d, resto→`round(interval * ef)`
  - **Error**: `new_ef = max(1.3, ef - 0.2)`, `interval = 1`
  - EF nunca baja de 1.3; `next_review = hoy + interval días`
  - Conserva toda la lógica de `mastery_level` y `consecutive_correct/incorrect` del Sprint 7
- Nueva función `get_concepts_due_today() -> list[Concept]`:
  - Devuelve conceptos clasificados con `DATE(next_review) <= DATE('now')`
  - Ordenados por `next_review` ascendente

### agents/review_agent.py
- Reescrito para usar `get_concepts_due_today()` en lugar del filtro `mastery < 3`
- Mensaje indica cuántos conceptos programa SM-2 para hoy e incluye el intervalo actual

### ui/app.py
- Badge en el título del Tab 2: `"📚 Aprendizaje (N pendientes)"` cuando hay conceptos por repasar
- Nueva sección **"📅 Para repasar hoy"** antes de Flashcards:
  - Lista conceptos con dominio, días desde último repaso e intervalo SM-2
  - Botón **"▶️ Repasar ahora"** que carga solo esos conceptos en la cola de flashcards

### tests/test_sprint8.py
- 5 verificaciones sin dependencia de API externa:
  1. Acierto actualiza EF correctamente (q=4 → EF estable en 2.5)
  2. Error baja EF 0.2 y resetea intervalo a 1
  3. EF nunca baja de 1.3
  4. Concepto con next_review=hoy aparece en `get_concepts_due_today`
  5. Concepto con next_review=mañana NO aparece
