# Sprint 34 — Bug Fix: Telegram + BD



## Bugs en scope

| ID | Bug | Archivo probable |
|----|-----|-----------------|
| BUG-01 | Dict crudo en bot en vez de texto | `bot/handlers.py` o `bot/nura_bridge.py` |
| BUG-02 | `/examen [categoría]` falla en producción | `bot/handlers.py`, `agents/exam_agent.py` |
| BUG-03 | `/repasar` redirige a la app web en vez de funcionar en Telegram | `bot/handlers.py`, `bot/nura_bridge.py` |
| BUG-04 | Conceptos sucios en BD (`7perfil`, `el mismo`, `y quien soy`) | Supabase SQL directo |

---

## BUG-01 — Dict crudo en bot

### Síntoma
El bot envía el objeto dict de Python en lugar del texto de la respuesta. Ejemplo: `{'output': 'Hola! Soy Nura...'}` en vez de `Hola! Soy Nura...`

### Causa probable
En `nura_bridge.py` o `handlers.py`, el resultado del grafo LangGraph se pasa directo a `message.reply_text()` sin extraer el campo de texto.

### DADO / CUANDO / ENTONCES

```
DADO:   Usuario escribe cualquier mensaje al bot
CUANDO: El bot procesa la respuesta del grafo LangGraph
ENTONCES: El bot envía solo el texto legible, no el dict completo
Y_NO:   El bot NO envía strings como "{'output': '...'}" ni representaciones de dict
```

### Fix esperado
```python
# MAL
await message.reply_text(result)

# BIEN — extraer el campo correcto del state
response_text = result.get("output") or result.get("response") or str(result)
await message.reply_text(response_text)
```

### Test requerido
```
test_bot_response_is_plain_text:
  - Mock del grafo que retorna {'output': 'Hola'}
  - Verificar que el mensaje enviado es 'Hola', no el dict
```

---

## BUG-02 — `/examen [categoría]` falla en producción

### Síntoma
El comando `/examen matemáticas` falla en producción. En local puede funcionar.

### Causa probable
- `context.args` es None o lista vacía cuando no hay categoría → no hay manejo de None
- O el `exam_agent` recibe la categoría en formato incorrecto

### DADO / CUANDO / ENTONCES

```
DADO:   Usuario envía /examen matemáticas en Telegram
CUANDO: El handler procesa context.args
ENTONCES: El bot inicia el examen de la categoría "matemáticas" o informa que no hay conceptos en esa categoría
Y_NO:   El bot NO se cuelga, NO envía error de Python, NO queda en silencio

DADO:   Usuario envía /examen (sin categoría)
CUANDO: El handler procesa context.args vacío
ENTONCES: El bot pregunta qué categoría quiere examinar o lista las disponibles
Y_NO:   El bot NO lanza excepción por context.args[0] con lista vacía
```

### Fix esperado
```python
# En handlers.py
async def examen_handler(update, context):
    categoria = context.args[0] if context.args else None
    try:
        resultado = await nura_bridge.run_exam(update.effective_user.id, categoria)
        await update.message.reply_text(resultado)
    except Exception as e:
        await update.message.reply_text("No pude iniciar el examen. Intenta con /examen [categoría].")
        logger.error(f"Error en /examen: {e}")
```

### Test requerido
```
test_examen_con_categoria:
  - context.args = ['matematicas']
  - Verificar que run_exam recibe 'matematicas'

test_examen_sin_categoria:
  - context.args = []
  - Verificar que run_exam recibe None, no lanza IndexError

test_examen_excepcion:
  - run_exam lanza Exception
  - Verificar que el usuario recibe mensaje de error legible
```

---

## BUG-03 — `/repasar` redirige a la app web

### Síntoma
El bot responde con un link a la app Streamlit en vez de iniciar la sesión de repaso SM-2 directamente en Telegram.

### Causa probable
El handler de `/repasar` tiene un fallback que envía la URL de la app, o nunca se conectó al `review_agent` vía `nura_bridge`.

### DADO / CUANDO / ENTONCES

```
DADO:   Usuario envía /repasar en Telegram
CUANDO: El bot procesa el comando
ENTONCES: El bot inicia la sesión de repaso con la primera flashcard pendiente directamente en el chat
Y_NO:   El bot NO envía links a streamlit, NO redirige a ninguna URL externa

DADO:   Usuario no tiene conceptos pendientes de repaso
CUANDO: El bot consulta la BD
ENTONCES: El bot responde "No tienes conceptos pendientes para hoy 🎉"
Y_NO:   El bot NO envía link a la app
```

### Fix esperado
```python
# En handlers.py — verificar que llama al bridge, no a una URL
async def repasar_handler(update, context):
    user_id = update.effective_user.id
    try:
        resultado = await nura_bridge.run_review(user_id)
        await update.message.reply_text(resultado)
    except Exception as e:
        await update.message.reply_text("Error al iniciar el repaso. Intenta de nuevo.")
        logger.error(f"Error en /repasar: {e}")

# En nura_bridge.py — verificar que run_review existe y llama al review_agent
async def run_review(telegram_user_id: int) -> str:
    user = get_user_by_telegram_id(telegram_user_id)
    if not user:
        return "Primero vincula tu cuenta con /vincular"
    # Llamar al review_agent, no retornar URL
    result = await graph.ainvoke({"mode": "review", "user_id": user.id})
    return result.get("output", "No hay conceptos pendientes hoy 🎉")
```

### Test requerido
```
test_repasar_no_envia_url:
  - Mock de run_review que retorna texto
  - Verificar que la respuesta NO contiene 'http' ni 'streamlit'

test_repasar_sin_conceptos:
  - run_review retorna mensaje vacío o lista vacía
  - Verificar que el usuario recibe mensaje amigable

test_repasar_usuario_no_vinculado:
  - get_user_by_telegram_id retorna None
  - Verificar que el usuario recibe instrucción de vinculación
```

---

## BUG-04 — Conceptos sucios en BD

### Acción
SQL directo en Supabase. No requiere código.

```sql
-- Paso 1: confirmar antes de borrar
SELECT id, term, user_id, created_at 
FROM concepts 
WHERE term IN ('7perfil', 'el mismo', 'y quien soy');

-- Paso 2: borrar solo si el SELECT confirma que son basura
DELETE FROM concepts 
WHERE term IN ('7perfil', 'el mismo', 'y quien soy');

-- Paso 3: verificar
SELECT COUNT(*) FROM concepts 
WHERE term IN ('7perfil', 'el mismo', 'y quien soy');
-- Debe retornar 0
```

### Prevención futura
En `capture_agent.py` agregar validación antes de guardar:
```python
TÉRMINOS_INVALIDOS = {"y quien soy", "el mismo", "no sé"}
if len(term.strip()) < 3 or term.strip().lower() in TÉRMINOS_INVALIDOS:
    return {"output": "Eso no parece un concepto para guardar. ¿Qué término quieres aprender?"}
```

---

## Criterio de cierre S34

- [ ] BUG-01: bot responde texto legible, nunca dict
- [ ] BUG-02: `/examen matemáticas` funciona; `/examen` sin args no rompe
- [ ] BUG-03: `/repasar` inicia flashcard en Telegram, no envía URL
- [ ] BUG-04: `SELECT COUNT(*) FROM concepts WHERE term IN (...)` = 0
- [ ] Todos los tests nuevos pasan localmente
- [ ] Deploy en Railway exitoso post-fix

