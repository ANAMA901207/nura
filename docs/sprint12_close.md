# Sprint 12 Close — Tutor Adaptativo Inteligente

## Resumen

Sprint 12 convierte Nura de un tracker pasivo a un tutor proactivo que detecta
patrones de aprendizaje, identifica debilidades del usuario y adapta su comportamiento
en tiempo real. Se implementó el motor de análisis de patrones, las intervenciones
proactivas y el nuevo agente de insights.

---

## Archivos creados

### `agents/insight_agent.py` (nuevo)
Agente de insights adaptativos que se activa con `mode='insight'` al inicio de cada
sesión diaria.

- **`insight_agent(state)`**: Lógica principal. Si hay < 5 conceptos clasificados
  retorna un mensaje de bienvenida estático sin llamar a la API. Con ≥ 5 conceptos,
  llama a Gemini con el perfil semanal del usuario para generar un mensaje personalizado
  de máximo 3 líneas.
- **`_build_insight_context()`**: Construye el texto de contexto para el LLM con
  métricas semanales, categorías débiles y últimos conceptos aprendidos.
- **`_build_static_insight()`**: Fallback estático cuando la API no está disponible.
  Genera un mensaje motivador usando solo datos de la BD.

### `tests/test_sprint12.py` (nuevo)
28 tests de regresión para las nuevas funcionalidades:

| Clase                              | Tests | Cobertura                                      |
|------------------------------------|-------|------------------------------------------------|
| `TestGetWeakCategories`            | 5     | Filtro por mastery y count                     |
| `TestGetNeglectedConcepts`         | 4     | Detección de conceptos sin actividad           |
| `TestInsightAgent`                 | 4     | Mensajes estáticos, fallback, BD vacía         |
| `TestRenderInsightBanner`          | 2     | Renderizado con y sin mensaje                  |
| `TestGetStrugglingConcepts`        | 3     | Filtro por fallos consecutivos                 |
| `TestGetLearningPreference`        | 3     | Detección de preferencia flashcards/chat       |
| `TestGetWeeklyInsightData`         | 3     | Claves, conteo semanal, BD vacía               |
| `TestCaptureAgentInsightPassthrough` | 2   | Pass-through de mode='insight'                 |
| `TestGraphCompilesWithInsightNode` | 2     | Compilación y presencia del nodo insight       |

---

## Archivos modificados

### `db/operations.py`
Se añadieron 5 nuevas funciones de análisis de patrones al bloque `# analytics`:

- **`get_weak_categories(user_id)`** → `list[dict]`
  Retorna categorías con > 2 conceptos y mastery promedio < 2.5, ordenadas ascendente.
  Cada dict tiene: `category`, `avg_mastery`, `count`.

- **`get_neglected_concepts(user_id, days=7)`** → `list[Concept]`
  Conceptos clasificados sin actividad (never reviewed o last_reviewed > N días) y
  capturados hace más de N días. Usa doble filtro `created_at < cutoff` para excluir
  conceptos recién añadidos.

- **`get_struggling_concepts(user_id, min_failures=3)`** → `list[Concept]`
  Conceptos con `consecutive_incorrect >= min_failures`, ordenados por fallo descendente.

- **`get_learning_preference(user_id)`** → `str`
  Heurística: retorna `'flashcards'` si `total_reviews > total_concepts * 2`,
  sino `'chat'`. Detecta si el usuario prefiere repasar por flashcards o por tutor.

- **`get_weekly_insight_data(user_id)`** → `dict`
  Agrega métricas de la semana en un solo dict:
  `conceptos_esta_semana`, `categoria_mas_fuerte`, `categoria_mas_debil`,
  `conceptos_dominados`, `racha`.

### `agents/state.py`
- Añadido campo `insight_message: str` al `NuraState`.
- Documentado `mode='insight'` en el docstring del TypedDict.

### `agents/capture_agent.py`
- Añadido check de prioridad -1 al inicio de `capture_agent()`: si
  `state.get("mode") == "insight"`, retorna inmediatamente con `mode='insight'`
  sin ejecutar ninguna heurística ni tocar la BD. Esto permite que la UI
  invoque el grafo con `mode='insight'` directamente para el banner diario.

### `agents/graph.py`
- Importado `insight_agent` desde `agents.insight_agent`.
- Añadido nodo `"insight"` al `StateGraph`.
- Añadida ruta `'insight' → "insight"` en `_route_after_capture()`.
- Añadida la constante `"insight": "insight"` en el dict de `add_conditional_edges`.
- Añadido `workflow.add_edge("insight", END)`.

### `ui/components.py`
- **`render_insight_banner(message: str)`** (nueva función): Renderiza el mensaje
  de `insight_agent` en un banner con fondo azul oscuro, borde izquierdo azul
  (`#89b4fa`) e ícono 🧠. No produce output si `message` está vacío.

### `ui/app.py`

**Imports:**
- Añadidos `get_neglected_concepts`, `get_weekly_insight_data` a las importaciones
  de `db.operations`.
- Añadido `render_insight_banner` a las importaciones de `ui.components`.

**`_empty_state()`:**
- Nuevo parámetro `mode: str = ""` para permitir invocar el grafo con un modo
  pre-establecido (usado para `mode='insight'`).
- Añadido `"insight_message": ""` al dict de estado inicial.

**`_invoke_with_timeout()`:**
- Nuevo parámetro `mode: str = ""` que se pasa a `_empty_state()`.
- Actualizado `_TIMEOUT_RESULT` para incluir `"insight_message": ""`.

**`_init_session()`:**
- Añadidas claves `insight_message` e `insight_date` al estado de sesión.

**`main()`:**
- Al inicio de cada sesión (primera carga del día), invoca el grafo con
  `mode='insight'` y almacena el mensaje en `st.session_state.insight_message`.
- Usa `st.session_state.insight_date` para no repetir la llamada en cada rerun.
- Llama a `render_insight_banner()` si hay mensaje.

**Historial de quiz:**
- Captura el retorno de `render_quiz()` como `quiz_results`.
- Si el score es < 60%, muestra un panel de intervención con botón
  "Sí, explícame" que activa una sesión de tutor con el mensaje:
  *"Explícame de forma diferente los conceptos que más me están costando"*.

**`_render_learning_profile()`:**
- Añadida sección "Insight semanal" al inicio del perfil con 4 métricas:
  conceptos esta semana, racha activa, conceptos dominados, estilo preferido.
- Banner de área a reforzar si `categoria_mas_debil` está disponible.

---

## Arquitectura del flujo insight

```
UI (main)
  │
  ├─ [primer load del día] → _invoke_with_timeout("", mode='insight')
  │      │
  │      ├─ graph.invoke(state con mode='insight')
  │      │      │
  │      │      └─ capture_agent
  │      │             │
  │      │             ├─ state.mode == 'insight' → retorna mode='insight'
  │      │             │
  │      │             └─ _route_after_capture → nodo "insight"
  │      │                    │
  │      │                    └─ insight_agent
  │      │                           │
  │      │                           ├─ < 5 conceptos → mensaje estático
  │      │                           ├─ sin API key   → fallback estático
  │      │                           └─ ≥ 5 + API key → Gemini personalizado
  │      │
  │      └─ st.session_state.insight_message = result['insight_message']
  │
  └─ render_insight_banner(st.session_state.insight_message)
```

---

## Resultados de tests

```
Sesión de tests (no-API):
  121/121 passed — 0 regressions (2:51 min)
  Incluye todos los tests de Sprint 12 y todos los sprints previos.

Sprint 12 aislado:
  28/28 passed (5.30 s)
```

Tests excluidos de la ejecución rápida (hacen llamadas reales a Gemini):
- `test_agents.py`
- `test_sprint4.py`
- `test_sprint10.py`

---

## Notas técnicas

**Singleton de insight por día**: El insight se genera una vez por día usando
`st.session_state.insight_date`. En recargas subsiguientes del mismo día, el
mensaje ya almacenado en `st.session_state.insight_message` se muestra sin
invocar el grafo.

**Fallback robusto**: El `insight_agent` nunca falla. Si Gemini no está disponible
(API key ausente, error 403, timeout), `_build_static_insight()` genera un mensaje
basado directamente en los datos de la BD.

**`_build_static_insight()` prioridad**: área más débil > área más fuerte > mensaje genérico.

**Intervención post-quiz**: Solo se muestra cuando `render_quiz()` retorna un dict
no vacío (quiz guardado) y el score es < 60%. El botón "Sí, explícame" envía una
pregunta al tutor sin necesidad de identificar los concept IDs individualmente.
