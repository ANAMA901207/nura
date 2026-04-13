# Bugfixes Post-Sprint 11 (Cerrado)

## Resultado: 108/108 tests pasados

---

## Bug 1 — UNIQUE(date, user_id) en daily_summaries

### Problema
El constraint `UNIQUE` en la tabla `daily_summaries` era solo sobre `date`, no sobre
`(date, user_id)`.  En un entorno multi-usuario, cuando dos usuarios intentaban crear
un resumen para el mismo día se lanzaba `sqlite3.IntegrityError: UNIQUE constraint
failed: daily_summaries.date`.

### Archivos modificados
**`db/schema.py`**

- `init_db()`: el `CREATE TABLE IF NOT EXISTS daily_summaries` ahora incluye
  `UNIQUE(date, user_id)` como constraint de tabla.  Bases de datos nuevas nacen
  con la restricción correcta.

- `_run_migrations()`: nueva migración **Sprint 11b** al final del bloque, idempotente:
  - Usa el índice nombrado `uq_daily_date_user` como marcador de migración aplicada.
  - Si el índice no existe (BD vieja con `date UNIQUE` solitario), ejecuta la
    técnica de recreación de tabla SQLite:
    1. `CREATE TABLE daily_summaries_new (... UNIQUE(date, user_id))`
    2. `INSERT OR IGNORE INTO daily_summaries_new SELECT ... FROM daily_summaries`
    3. `DROP TABLE daily_summaries`
    4. `ALTER TABLE daily_summaries_new RENAME TO daily_summaries`
  - Recrea los índices perdidos al DROP TABLE: `uq_daily_date_user` e
    `idx_summaries_user_date`.
  - Idempotente: si la migración ya se aplicó, la detección del índice hace no-op.

---

## Bug 2 — Detección de preguntas en frases > 4 palabras

### Problema
Frases como `"no entiendo qué es blockchain"` (5 palabras) eran capturadas como
**chat** por `_is_chat` (que usaba `startswith` sin límite de longitud), dando una
respuesta canned corta en lugar de enrutar al tutor para una explicación real.
Frases como `"explícame cómo funciona la regresión logística"` no eran detectadas por
ninguna regla y caían como **término** a capturar.

### Archivos modificados
**`agents/capture_agent.py`**

`_is_chat` — excepción para inputs de **> 4 palabras**:
- Si la frase inicia con una expresión de pregunta implícita y no es una coincidencia
  exacta con la frase de chat, se devuelve `False` para que `_is_question` lo procese.
- Comportamiento conservado: `"no entiendo"` (≤ 4 palabras) sigue siendo chat.

`_is_question` — tres nuevas reglas:
1. Se añaden `"explicame"`, `"dime"`, `"cuentame"` a `_QUESTION_STARTERS` (primera
   palabra interrogativa).
2. `_QUESTION_PHRASE_STARTERS` (nueva lista): si el input tiene **> 4 palabras** y
   comienza con `"no entiendo"`, `"no se"`, `"como funciona"`, `"que es"`,
   `"explicame"`, `"cual es la diferencia"`, `"para que sirve"` etc. → pregunta.
3. `_SENTENCE_VERBS` (nuevo set): si el input tiene **> 6 palabras** y contiene
   verbos de oración como `"funciona"`, `"sirve"`, `"entiendo"`, `"puede"`,
   `"explica"`, `"calcula"`, etc. → probablemente frase, no término técnico compuesto.
   También detecta inicios no-técnicos (`"no"`, `"me"`, `"yo"`, `"te"`, `"se"`).

### Ejemplos resueltos
| Input | Antes | Después |
|-------|-------|---------|
| `"no entiendo qué es blockchain"` (5 palabras) | chat | **question** |
| `"explícame qué es la tasa de descuento"` | capture | **question** |
| `"no sé cómo funciona la regresión logística"` | capture | **question** |
| `"cómo funciona el algoritmo de spaced repetition"` | question | question ✓ |
| `"no entiendo"` | chat | chat ✓ |
| `"tasa de interés nominal"` | capture | capture ✓ |
| `"valor presente neto ajustado por riesgo"` | capture | capture ✓ |

---

## Bug 3 — Reclasificar términos ya clasificados en lugar de lanzar error

### Problema
Cuando el usuario escribía un término que ya existía en la BD con `is_classified=True`,
`capture_agent` lanzaba `ValueError: El término 'X' ya existe y está clasificado.`
En la UI esto aparecía como `st.error("Error al procesar: ...")` en lugar de un
comportamiento útil.

### Archivos modificados
**`agents/capture_agent.py`**
- Eliminado el `raise ValueError(...)` para términos ya clasificados.
- Ahora retorna `mode='reclassify'` para **cualquier término existente**, esté
  clasificado o no, con mensaje diferenciado:
  - `is_classified=False`: `"Reintentando clasificar 'X'..."`
  - `is_classified=True`: `"Ya conozco 'X' — lo reclasificaré con el nuevo contexto."`
- El concepto pasa por `classifier_agent → connector_agent` exactamente igual que
  en una captura nueva, usando el `user_context` para enriquecer la reclasificación.

**`ui/app.py`**
- `_BADGES` amplíado con `"reclassify": ("#cba6f7", "🔄 Reclasificado")`.
- Condición de renderizado ampliada: `mode in ("capture", "reclassify")` muestra la
  concept card actualizada.
- Para `mode='reclassify'` se muestra el mensaje amigable en morado antes de la
  tarjeta: *"Ya conocía este término — lo reclasifiqué con el nuevo contexto."*

---

## Bug adicional — Manejo amigable de errores 403 y de API de Gemini

### Problema
Un error 403 (`PERMISSION_DENIED`, clave inválida) propagaba el traceback completo
hasta `st.error(f"Error al procesar: {exc}")` en la UI.

### Archivos modificados
**`agents/tutor_agent.py`**
- `_is_auth_error(exc)`: detecta 403, `PERMISSION_DENIED`, `API_KEY_INVALID`,
  `SERVICE_DISABLED`, `FORBIDDEN`.
- `_friendly_api_error(exc)`: convierte cualquier error del LLM en mensaje legible.
- `_call_gemini()`: detecta errores de auth y lanza `PermissionError` descriptivo
  sin reintentar.
- `tutor_agent()`: si falta `GOOGLE_API_KEY` retorna mensaje amigable en `response`
  en lugar de `EnvironmentError`; todo el bloque LLM en `try/except Exception`.

**`agents/quiz_agent.py`**
- Mismo patrón: falta de clave y errores 403 retornan `response` amigable.

**`ui/app.py` (`_invoke_with_timeout`)**
- Capa de seguridad final: captura excepciones que escapen del grafo y retorna
  dict con `response` amigable distinguiendo errores 403 del resto.

---

## Bug adicional — UNIQUE constraint en daily_summaries ya corregido arriba

*(Incluido en Bug 1 — ver arriba)*

---

## Tests nuevos — `tests/test_bugfixes.py`

20 tests en 3 clases:

| Clase | Tests | Qué verifica |
|-------|-------|--------------|
| `TestBug1HtmlRendering` | 4 | Sin `st.write()`/`st.text()` para campos Concept; sin `_html.escape()` en analogy; examples y flashcard usan `<div>` HTML |
| `TestBug2IsQuestion` | 12 | `_is_chat` conserva comportamiento para ≤ 4 palabras; `_is_question` detecta frases > 4 palabras con patrones interrogativos; términos técnicos siguen como capture |
| `TestBug3ReclassifyClassified` | 4 | Término clasificado → `mode='reclassify'`; término sin clasificar → `mode='reclassify'`; término nuevo → `mode='capture'`; badge `reclassify` definido en app.py |

---

## Suite completa
```
108/108 passed  (4:03, incluye llamadas reales a Gemini API)
0 regresiones
```
