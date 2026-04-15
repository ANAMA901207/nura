# Bugfix: Detección de chat mejorada + Eliminar concepto pendiente

## Fecha
2026-04-14

## Archivos modificados
- `agents/capture_agent.py`
- `ui/app.py`
- `docs/bugfix_chat_detection_delete_pending_close.md` (este archivo)

---

## Fix 1 — `agents/capture_agent.py`: detección de preguntas conversacionales con pronombres

### Problema
Las frases `"Tu quien eres"` y `"Y tu quien eres"` estaban en `_CHAT_PHRASES` con
mayúsculas, pero `_normalize()` convierte todo a minúsculas antes de comparar →
nunca hacían match → Nura intentaba capturarlas como conceptos técnicos.

Además faltaban variantes comunes con pronombres interrogativos.

### Solución
- Corregidos los dos ítems existentes a minúsculas (`"tu quien eres"`, `"y tu quien eres"`).
- Agregadas las variantes:
  `"y tu"`, `"tu quien"`, `"quien eres tu"`, `"que eres tu"`,
  `"como te llamas"`, `"como te llama"`, `"como te llaman"`,
  `"cual es tu nombre"`, `"cual es tu proposito"`, `"cual es tu funcion"`,
  `"para que eres"`, `"que haces tu"`.

---

## Fix 2 — `ui/app.py`: botón "Eliminar" en conceptos pendientes de clasificación

### Problema
La sección de conceptos pendientes solo ofrecía "Reintentar". No había forma de
eliminar un concepto sin clasificar desde la UI.

### Solución
- Layout cambiado de `[4, 1]` a `[4, 1, 1]` (label / Reintentar / Eliminar).
- El botón "Eliminar" muestra una confirmación inline (`¿Eliminar «término»?`)
  con botones Sí / No gestionados con `st.session_state`.
- Al confirmar llama a `delete_concept(uc.id, user_id=uid)` (importado al inicio
  del módulo) y hace `st.rerun()`.

---

## Resultado del harness

```
286 passed, 3 failed (pre-existentes, API key 403 PERMISSION_DENIED — no relacionados con este fix)
```

Los 3 fallos (`test_classifier_fills_category_and_flashcard`,
`test_two_related_concepts_generate_connection`, `test_tutor_uses_bd_context`)
requieren una llamada real a Gemini y fallan porque la API key local está
comprometida. No existían antes de este fix y no son causados por él.
