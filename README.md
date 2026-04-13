# Nura — Sistema de Aprendizaje Adaptativo

Nura es una aplicación de aprendizaje adaptativo con memoria persistente. Captura términos que el usuario quiere aprender, los clasifica automáticamente con un LLM, construye un grafo de conocimiento entre conceptos, y actúa como tutor conversacional que usa el conocimiento acumulado como contexto.

---

## Funcionalidades principales

| Módulo | Qué hace |
|---|---|
| **Captura** | Detecta si el input es un término nuevo, una pregunta o una solicitud de repaso |
| **Clasificador** | Enriquece cada término con categoría, explicación, analogía, ejemplo y flashcard vía Gemini |
| **Conector** | Encuentra vínculos semánticos entre el nuevo concepto y los anteriores |
| **Tutor** | Responde preguntas usando los conceptos guardados como contexto personal |
| **Repaso** | Sugiere hasta 3 conceptos para repasar según nivel de dominio y antigüedad |
| **Mapa** | Grafo interactivo pyvis con filtros por categoría y dominio, y panel de detalle por nodo |
| **Flashcards** | Baraja de tarjetas con frente/reverso generadas por el clasificador |

---

## Estructura del proyecto

```
nura/
├── agents/
│   ├── state.py            # NuraState — TypedDict compartido entre nodos
│   ├── graph.py            # StateGraph con 5 nodos y enrutamiento condicional
│   ├── capture_agent.py    # Nodo 1: detecta modo (capture / question / review / reclassify)
│   ├── classifier_agent.py # Nodo 2: enriquece el concepto vía Gemini
│   ├── connector_agent.py  # Nodo 3: detecta y guarda conexiones semánticas
│   ├── tutor_agent.py      # Nodo 4: responde preguntas con contexto de la BD
│   └── review_agent.py     # Nodo 5: genera sesión de repaso personalizada
├── db/
│   ├── models.py           # Dataclasses: Concept, Connection, DailySummary
│   ├── schema.py           # SQLite init + migraciones incrementales
│   └── operations.py       # Funciones CRUD puras (sin ORM)
├── tools/
│   ├── classifier_tool.py  # classify_concept() → dict JSON + ClassificationError
│   └── connector_tool.py   # find_connections() → list[dict]
├── ui/
│   ├── app.py              # Aplicación Streamlit (2 tabs)
│   └── components.py       # Componentes reutilizables
├── tests/
│   ├── test_db.py          # 6 tests de la capa de base de datos
│   ├── test_agents.py      # 5 tests del pipeline de agentes
│   ├── test_ui.py          # 5 tests de componentes de UI
│   ├── test_sprint4.py     # 5 tests del tutor y modo repaso
│   ├── test_sprint5.py     # 5 tests de clasificación diferida
│   └── test_sprint6.py     # 5 tests del mapa y filtros
├── docs/                   # Especificaciones y cierres de cada sprint
├── .streamlit/config.toml  # Tema oscuro Catppuccin Mocha
└── .env                    # API keys (no versionar)
```

---

## Requisitos

- Python 3.10+
- Cuenta de Google AI Studio con `GOOGLE_API_KEY`

### Dependencias principales

| Paquete | Versión | Uso |
|---|---|---|
| `streamlit` | 1.56.0 | Interfaz web |
| `langgraph` | 1.1.6 | Orquestación de agentes |
| `langchain-google-genai` | 4.2.1 | Cliente Gemini |
| `pyvis` | 0.3.2 | Mapa de conocimiento interactivo |
| `python-dotenv` | 1.2.1 | Carga de variables de entorno |

---

## Instalación

```bash
# 1. Clonar / descomprimir el proyecto
cd nura

# 2. Crear entorno virtual (opcional pero recomendado)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Instalar dependencias
pip install streamlit langgraph langchain-google-genai pyvis python-dotenv

# 4. Configurar credenciales
# Crear el archivo .env en la raíz del proyecto:
```

```dotenv
GOOGLE_API_KEY=tu_clave_aqui
GEMINI_MODEL=gemini-2.5-flash   # o gemini-2.0-flash, gemini-1.5-flash
```

```bash
# 5. Inicializar la base de datos y lanzar la app
streamlit run ui/app.py
```

La aplicación queda disponible en `http://localhost:8501`.

---

## Uso

### Tab 1 — Chat de captura

- **Escribe un término** (ej: `tasa de interés`) → Nura lo guarda, clasifica y conecta con conceptos previos.
- **Haz una pregunta** (ej: `¿qué es la amortización?`) → el Tutor responde usando tu base de conocimiento personal.
- **Pide un repaso** (ej: `quiero repasar`) → el agente de repaso lista los conceptos con dominio más bajo.
- **Campo de contexto** (opcional) → indica dónde escuchaste el término para que el clasificador sea más preciso.
- **Botón 🔁 Sesión de repaso** → acceso directo al modo repaso.

### Tab 2 — Aprendizaje

- **Resumen de hoy**: conceptos capturados, conexiones nuevas y flashcards completadas.
- **Mis conceptos**: tabla agrupada por categoría. Los conceptos sin clasificar muestran ⚠️ con botón **Reintentar** y formulario **✏️ Corregir**.
- **Flashcards**: una tarjeta a la vez con botones Voltear y Siguiente.
- **Mapa de conocimiento**: grafo interactivo con filtros de categoría y nivel de dominio. Selecciona cualquier nodo en el selectbox para ver su panel de detalle con todas sus conexiones explicadas.

---

## Arquitectura del pipeline

```
Usuario escribe input
        │
   capture_agent          ← detecta modo sin LLM (heurística)
        │
        ├─ mode='capture'     ──→ classifier_agent ──→ connector_agent ──→ END
        ├─ mode='reclassify'  ──→ classifier_agent ──→ connector_agent ──→ END
        ├─ mode='question'    ──→ tutor_agent ──────────────────────────→ END
        └─ mode='review'      ──→ review_agent ─────────────────────────→ END
```

- **`capture_agent`**: sin LLM. Clasifica el input en 4 modos por heurísticas de palabras clave.
- **`classifier_agent`**: llama a Gemini. Si falla lanza `ClassificationError` → el concepto queda en BD con `is_classified=False` para reintento.
- **`connector_agent`**: llama a Gemini. Devuelve lista vacía si hay ≤ 1 concepto en BD.
- **`tutor_agent`**: llama a Gemini con el contexto de todos los conceptos guardados.
- **`review_agent`**: sin LLM. Filtra por `mastery_level < 3` o `last_reviewed > 3 días`.

---

## Tests

```bash
# Todos los harnesses son deterministas excepto test_agents y test_sprint4
# (que hacen llamadas reales a Gemini)

python tests/test_db.py         # 6/6  — capa de base de datos
python tests/test_ui.py         # 5/5  — componentes de UI (streamlit mockeado)
python tests/test_sprint4.py    # 5/5  — tutor + repaso
python tests/test_sprint5.py    # 5/5  — clasificación diferida
python tests/test_sprint6.py    # 5/5  — mapa y filtros
```

---

## Modelo de datos

```
Concept
  id, term*, category, subcategory, explanation, examples, analogy,
  context, user_context, flashcard_front, flashcard_back,
  mastery_level (0-5), created_at, last_reviewed, is_classified

Connection
  id, concept_id_a → Concept, concept_id_b → Concept, relationship, created_at

DailySummary
  id, date*, concepts_captured, new_connections, concepts_reviewed
```

`*` = campo UNIQUE en la BD.  Todos los dataclasses son `frozen=True`.

---

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `GOOGLE_API_KEY` | Sí | Clave de Google AI Studio |
| `GEMINI_MODEL` | No | Modelo a usar (default: `gemini-2.0-flash`) |

> **Nota sobre cuotas:** el plan gratuito de Gemini tiene un límite de ~20 requests/día para algunos modelos. Si los agentes no responden, cambia `GEMINI_MODEL` a `gemini-2.5-flash` o `gemini-1.5-flash` en el `.env`.

---

## Decisiones de diseño

- **SQLite nativo** (`sqlite3`) sin ORM — cero dependencias extras, fácil de inspeccionar.
- **Dataclasses `frozen=True`** — los objetos del dominio son inmutables; solo la BD puede cambiarlos.
- **`ClassificationError`** — encapsula cualquier fallo del API en un tipo único que los agentes capturan sin importar la causa.
- **`is_classified`** — permite persistir términos aunque el clasificador falle: el usuario puede reintentar sin perder datos.
- **Timeout de 30 s** en `graph.invoke()` vía `ThreadPoolExecutor` — la UI nunca se cuelga indefinidamente.
- **Streamlit `st.cache_resource`** — el grafo LangGraph se construye una sola vez por proceso de servidor.
