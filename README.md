# Nura — Sistema de Aprendizaje Adaptativo

Nura es una aplicación de aprendizaje adaptativo con memoria persistente y multi-usuario. Captura términos que el usuario quiere aprender, los clasifica automáticamente con Gemini, construye un grafo de conocimiento entre conceptos, actúa como tutor conversacional personalizado y programa repasos mediante el algoritmo SM-2.

> **Sprint 22** — Supabase/PostgreSQL en producción, SQLite local para desarrollo y tests.

---

## Funcionalidades

| Módulo | Qué hace |
|---|---|
| **Captura** | Detecta si el input es un término, pregunta, repaso o corrección ortográfica |
| **Clasificador** | Enriquece cada término con categoría, explicación, analogía, ejemplo y flashcard vía Gemini |
| **Conector** | Detecta y guarda vínculos semánticos entre el nuevo concepto y los anteriores |
| **Tutor** | Responde preguntas con el contexto personal del usuario, búsqueda web y analogías adaptadas al perfil profesional |
| **Repaso SM-2** | Programa flashcards con el algoritmo SuperMemo 2 según rendimiento histórico |
| **Quiz adaptativo** | Genera preguntas de opción múltiple y ofrece explicación personalizada al fallar |
| **Mapa de conocimiento** | Grafo interactivo pyvis; click en nodo filtra la vista al concepto y sus conexiones directas |
| **Diagrama automático** | Genera diagramas SVG explicativos desde las respuestas del tutor |
| **Motivador** | Banner motivacional con mensajes personalizados según racha y rendimiento |
| **Detector de conceptos** | Extrae términos técnicos nuevos de las respuestas del tutor para sugerirlos |
| **Autenticación** | Registro y login con bcrypt; cada usuario tiene su propio espacio de datos |
| **Onboarding** | Recoge profesión, área de aprendizaje y nivel técnico para personalizar todos los agentes |

---

## Estructura del proyecto

```
nura/
├── agents/
│   ├── state.py              # NuraState — TypedDict compartido entre nodos
│   ├── graph.py              # StateGraph con enrutamiento condicional
│   ├── capture_agent.py      # Detecta modo: capture / question / review / quiz / clarify
│   ├── classifier_agent.py   # Enriquece el concepto vía Gemini (perfil-aware)
│   ├── connector_agent.py    # Detecta conexiones semánticas entre conceptos
│   ├── tutor_agent.py        # Responde con contexto personal + búsqueda web
│   ├── review_agent.py       # Genera sesión de repaso por SM-2 y antigüedad
│   ├── insight_agent.py      # Genera insights adaptativos semanales
│   └── motivator_agent.py    # Genera mensajes motivacionales personalizados
├── db/
│   ├── models.py             # Dataclasses: Concept, Connection, DailySummary, User
│   ├── schema.py             # Dual-mode: SQLite local ó PostgreSQL/Supabase
│   └── operations.py         # Funciones CRUD (sin ORM), compatibles con ambos motores
├── tools/
│   ├── classifier_tool.py    # classify_concept() → LangGraph @tool
│   ├── connector_tool.py     # find_connections() → LangGraph @tool
│   ├── concept_detector_tool.py  # detect_new_concepts() — extrae términos técnicos
│   └── diagram_tool.py       # generate_diagram_svg() — diagramas SVG desde texto
├── ui/
│   ├── app.py                # Aplicación Streamlit principal
│   ├── components.py         # Componentes reutilizables (cards, mapa, flashcards…)
│   └── auth.py               # Pantalla de login / registro / onboarding
├── tests/                    # 288 tests — todos deterministas salvo test_sprint4
│   ├── test_db.py
│   ├── test_agents.py
│   ├── test_sprint4.py       # Requiere GOOGLE_API_KEY activa (Gemini)
│   ├── test_sprint[5-22].py
│   └── test_bugfixes.py
├── docs/                     # Specs y cierres de cada sprint
├── design/                   # Favicon y assets visuales
├── .streamlit/config.toml    # Tema oscuro Catppuccin Mocha
└── .env                      # API keys y DATABASE_URL (no versionar)
```

---

## Requisitos

- Python 3.10+
- Cuenta de Google AI Studio con `GOOGLE_API_KEY`
- (Opcional) Instancia de Supabase o PostgreSQL para producción

### Dependencias

| Paquete | Versión | Uso |
|---|---|---|
| `streamlit` | 1.56.0 | Interfaz web |
| `langgraph` | 1.1.6 | Orquestación del pipeline de agentes |
| `langchain-google-genai` | 4.2.1 | Cliente Gemini |
| `langchain-core` | 1.2.24 | Base de LangChain |
| `pyvis` | 0.3.2 | Mapa de conocimiento interactivo |
| `python-dotenv` | 1.2.1 | Carga de variables de entorno |
| `bcrypt` | 5.0.0 | Hashing de contraseñas |
| `Pillow` | 12.0.0 | Generación del favicon y assets |
| `duckduckgo-search` | 8.1.1 | Búsqueda web desde el tutor |
| `psycopg2-binary` | 2.9.11 | Conector PostgreSQL/Supabase |
| `typing-extensions` | 4.15.0 | TypedDict en Python < 3.11 |

---

## Instalación

```bash
# 1. Clonar el proyecto
git clone https://github.com/ANAMA901207/nura.git
cd nura

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Instalar dependencias
pip install -r requirements.txt
```

### Variables de entorno

Crear el archivo `.env` en la raíz del proyecto:

```dotenv
# Requerida: clave de Google AI Studio
GOOGLE_API_KEY=tu_clave_aqui

# Opcional: modelo Gemini a usar (default: gemini-2.0-flash)
GEMINI_MODEL=gemini-2.0-flash

# Opcional: URL de Supabase/PostgreSQL para producción
# Si no está definida, Nura usa SQLite local (db/nura.db)
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

```bash
# 4. Lanzar la app
streamlit run ui/app.py
```

La aplicación queda disponible en `http://localhost:8501`.

---

## Base de datos dual

Nura selecciona el motor automáticamente según el entorno:

| Situación | Motor | Cuándo |
|---|---|---|
| `DATABASE_URL` en `.env` | PostgreSQL (Supabase) | Producción / multi-dispositivo |
| Sin `DATABASE_URL` | SQLite (`db/nura.db`) | Desarrollo local y todos los tests |

El esquema y las operaciones CRUD son idénticos en ambos motores. Al conectar a Supabase por primera vez, `init_db()` crea todas las tablas automáticamente.

---

## Uso

### Vistas principales

**Descubrir** — Chat de captura y tutor:
- Escribe un término (`tasa de interés`) → Nura lo guarda, clasifica y conecta.
- Haz una pregunta (`¿qué es la amortización?`) → el Tutor responde con analogías adaptadas a tu profesión.
- Nura detecta términos técnicos nuevos en la respuesta y te ofrece guardarlos.
- Corrección ortográfica automática de términos.

**Dominar** — Repaso y quiz:
- Flashcards con SM-2: el algoritmo programa cuándo volver a ver cada concepto según tus aciertos.
- Quiz de opción múltiple generado por Gemini con retroalimentación personalizada.
- Conceptos debidos hoy destacados.

**Conectar** — Mapa de conocimiento:
- Grafo interactivo pyvis con todos tus conceptos.
- Click en un nodo → filtra el mapa al concepto y sus conexiones directas.
- Panel de detalle con explicación, analogía y relaciones semánticas.
- Filtros por categoría y nivel de dominio.
- Edición y eliminación de conceptos desde tarjetas.

---

## Arquitectura del pipeline

```
Usuario escribe input
        │
   capture_agent          ← detecta modo sin LLM (heurísticas + spell-check)
        │
        ├─ capture     ──→ classifier_agent ──→ connector_agent ──→ END
        ├─ reclassify  ──→ classifier_agent ──→ connector_agent ──→ END
        ├─ question    ──→ tutor_agent ─────────────────────────→ END
        ├─ review      ──→ review_agent ────────────────────────→ END
        └─ clarify     ──→ [UI presenta opciones] ──────────────→ END
```

- **`capture_agent`**: sin LLM. Detecta modo por palabras clave + heurísticas de longitud.
- **`classifier_agent`**: Gemini. Genera categoría, explicación, analogía y flashcard adaptados al perfil.
- **`connector_agent`**: Gemini. Devuelve lista vacía si hay ≤ 1 concepto en BD.
- **`tutor_agent`**: Gemini + DuckDuckGo. Adapta analogías a la profesión del usuario.
- **`review_agent`**: sin LLM. SM-2 + filtro por antigüedad.
- **`insight_agent`**: Gemini. Genera insight semanal con métricas reales de la BD.
- **`motivator_agent`**: Gemini. Mensaje motivacional según racha y rendimiento.

---

## Tests

```bash
# Ejecutar todos los tests (requiere que DATABASE_URL NO esté definida)
python -m pytest tests/ -v --tb=short -q

# Resultado esperado: 288 passed (salvo test_sprint4 si no hay API key activa)
```

Los tests usan SQLite en memoria o archivos temporales; nunca tocan la BD de producción.

---

## Modelo de datos

```
User
  id, username, password_hash, created_at,
  profession, learning_area, tech_level

Concept  (UNIQUE: term + user_id)
  id, term, category, subcategory, explanation, examples,
  analogy, context, user_context,
  flashcard_front, flashcard_back,
  mastery_level (0–5), created_at, last_reviewed, is_classified,
  consecutive_correct, consecutive_incorrect, total_reviews,
  next_review, sm2_interval, sm2_ef,
  user_id → User

Connection
  id, concept_id_a → Concept, concept_id_b → Concept,
  relationship, created_at, user_id → User

DailySummary  (UNIQUE: date + user_id)
  id, date, concepts_captured, new_connections,
  concepts_reviewed, user_id → User
```

---

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `GOOGLE_API_KEY` | Sí | Clave de Google AI Studio |
| `GEMINI_MODEL` | No | Modelo Gemini (default: `gemini-2.0-flash`) |
| `DATABASE_URL` | No | URL PostgreSQL/Supabase; sin ella usa SQLite |

> **Nota sobre cuotas:** el plan gratuito de Gemini tiene límite de requests/minuto. Si los agentes no responden, espera unos segundos o cambia `GEMINI_MODEL` a `gemini-1.5-flash`.

---

## Decisiones de diseño

- **Base de datos dual (Sprint 22)**: SQLite para desarrollo/tests, PostgreSQL para producción. La capa `_NuraConn` abstrae las diferencias de placeholder (`?` vs `%s`) y `lastrowid` vs `RETURNING id`.
- **Sin ORM**: `sqlite3` / `psycopg2` nativos — cero abstracción innecesaria, fácil de inspeccionar.
- **Dataclasses `frozen=True`**: los objetos del dominio son inmutables; solo la BD puede cambiarlos.
- **Multi-usuario**: cada `Concept`, `Connection` y `DailySummary` tiene `user_id`; los datos de distintos usuarios nunca se mezclan.
- **SM-2**: el algoritmo SuperMemo 2 ajusta `sm2_interval` y `sm2_ef` por concepto según cada revisión.
- **Perfil de usuario**: `profession`, `learning_area` y `tech_level` se inyectan en todos los prompts para que el clasificador y el tutor usen analogías del dominio correcto.
- **Timeout de 45 s** en `graph.invoke()` vía `ThreadPoolExecutor` — la UI nunca se cuelga.
- **`ClassificationError`**: encapsula cualquier fallo de API; el concepto queda en BD con `is_classified=False` para reintento posterior.
- **Streamlit `st.cache_resource`**: el grafo LangGraph se construye una sola vez por proceso de servidor.
