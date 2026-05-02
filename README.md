# Nura — Sistema de Aprendizaje Adaptativo

Nura es una aplicación de aprendizaje adaptativo con memoria persistente y multi-usuario. Captura términos que el usuario quiere aprender, los clasifica automáticamente con Gemini, construye un grafo de conocimiento entre conceptos, actúa como tutor conversacional personalizado y programa repasos mediante el algoritmo SM-2.

> **Estado actual** — SQLite local para desarrollo y tests; PostgreSQL/Supabase en producción. Bot de Telegram opcional (webhook FastAPI), jerarquía de conceptos, examen de certificación por categoría, TTS y búsqueda web vía paquete `ddgs` (DuckDuckGo).

---

## Funcionalidades

| Módulo | Qué hace |
|--------|----------|
| **Captura** | Detecta modo: chat, término, pregunta, repaso, quiz, corrección ortográfica, ambigüedad, re-clasificación o búsqueda web antes de clasificar |
| **Clasificador** | Enriquece cada término con categoría, explicación, analogía, ejemplo y flashcard vía Gemini |
| **Conector** | Detecta y guarda vínculos semánticos entre el nuevo concepto y los anteriores |
| **Jerarquía** | Tras clasificar, infiere relaciones padre/hijo (p. ej. «es tipo de») y las persiste en `concept_hierarchy` |
| **Tutor** | Responde preguntas con el contexto personal del usuario, herramientas de BD/jerarquía, búsqueda web y analogías adaptadas al perfil |
| **Repaso SM-2** | Programa flashcards con SuperMemo 2 según rendimiento histórico |
| **Quiz adaptativo** | Genera preguntas de opción múltiple y ofrece explicación personalizada al fallar |
| **Examen** | Certificación por categoría (UI «Dominar» y bot Telegram `/examen`) con evaluación agregada |
| **Mapa de conocimiento** | Grafo interactivo pyvis; clic en nodo filtra al concepto y sus conexiones directas |
| **Diagrama automático** | Genera diagramas SVG explicativos desde las respuestas del tutor |
| **Insights** | Al iniciar sesión puede generarse un insight semanal con métricas reales de la BD |
| **Motivador** | Banner motivacional con mensajes personalizados según racha y rendimiento |
| **Detector de conceptos** | Extrae términos técnicos nuevos de las respuestas del tutor para sugerirlos |
| **Progreso** | Gráficos de actividad con `pandas` / Streamlit (Sprint 31) |
| **Autenticación** | Registro y login con bcrypt; cada usuario tiene su propio espacio de datos |
| **Onboarding** | Profesión, área de aprendizaje y nivel técnico; meta diaria de conceptos y hora de recordatorio |
| **Telegram** | Captura y tutor por chat; recordatorios programados; TTS opcional (`gTTS` + `pydub`; voz OGG requiere **ffmpeg** en el servidor) |

---

## Estructura del proyecto

```
nura/
├── agents/
│   ├── state.py              # NuraState — TypedDict compartido entre nodos
│   ├── graph.py              # StateGraph con enrutamiento condicional
│   ├── capture_agent.py      # Modos: chat, capture, question, review, quiz, insight, clarify…
│   ├── classifier_agent.py   # Enriquece el concepto vía Gemini (perfil-aware)
│   ├── connector_agent.py    # Conexiones semánticas entre conceptos
│   ├── hierarchy_agent.py    # Relaciones jerárquicas tras clasificar
│   ├── tutor_agent.py        # Tutor con herramientas y búsqueda web
│   ├── review_agent.py       # Sesión de repaso SM-2
│   ├── quiz_agent.py         # Quiz de opción múltiple
│   ├── exam_agent.py         # Examen por categoría (preguntas + evaluación)
│   ├── insight_agent.py      # Insights adaptativos semanales
│   └── motivator_agent.py    # Mensajes motivacionales
├── bot/
│   ├── main.py               # FastAPI + webhook Telegram; healthcheck GET /health
│   ├── handlers.py           # Comandos (/capturar, /examen, vinculación…)
│   ├── nura_bridge.py        # Puente al grafo y operaciones de BD
│   ├── scheduler.py          # Recordatorios diarios
│   └── tts.py                # Texto a voz para mensajes de voz
├── db/
│   ├── models.py             # Concept, Connection, DailySummary, User…
│   ├── schema.py             # Dual-mode: SQLite local ó PostgreSQL/Supabase
│   └── operations.py         # CRUD sin ORM; jerarquía, sesiones de examen, Telegram…
├── tools/
│   ├── classifier_tool.py    # classify_concept()
│   ├── connector_tool.py     # find_connections()
│   ├── concept_detector_tool.py
│   ├── concept_lookup_tool.py
│   ├── db_tools.py           # Tools formales LangChain (Sprint 19)
│   ├── diagram_tool.py       # SVG desde texto
│   ├── hierarchy_tool.py     # lookup_hierarchy
│   ├── search_tool.py        # web_search() vía ddgs (DuckDuckGo)
│   ├── web_search_tool.py    # @tool LangChain para el tutor
│   └── tutor_graph_tools.py
├── ui/
│   ├── app.py                # Aplicación Streamlit principal
│   ├── components.py         # Cards, mapa, flashcards, examen…
│   └── auth.py               # Login / registro / onboarding
├── tests/                    # ~363 tests — mayoría deterministas; test_sprint4 usa Gemini real si hay API key
├── docs/                     # Specs y cierres de sprints
├── design/                   # Favicon y assets
├── .streamlit/config.toml    # Tema oscuro Catppuccin Mocha
└── .env                      # API keys y URLs (no versionar)
```

---

## Requisitos

- Python 3.10+
- Cuenta de Google AI Studio con `GOOGLE_API_KEY`
- (Opcional) Instancia de Supabase o PostgreSQL para producción
- (Opcional) **ffmpeg** en el PATH si usás TTS en Telegram con conversión a OGG

### Dependencias principales

| Paquete | Uso |
|---------|-----|
| `streamlit` | Interfaz web |
| `pandas` | Gráficos de progreso en la UI |
| `langgraph`, `langchain-google-genai`, `langchain-core` | Grafo de agentes y Gemini |
| `pyvis` | Mapa de conocimiento |
| `python-dotenv` | Variables de entorno |
| `bcrypt` | Contraseñas |
| `Pillow` | Favicon y diagramas |
| `ddgs` | Búsqueda web (DuckDuckGo) sin API key |
| `psycopg2-binary` | PostgreSQL / Supabase |
| `typing-extensions` | TypedDict en Python 3.10 |
| `python-telegram-bot`, `fastapi`, `uvicorn`, `httpx` | Bot y webhook |
| `gTTS`, `pydub` | TTS para Telegram |

Versiones pinnadas en `requirements.txt`.

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
# Requerida para clasificador, tutor, quiz, diagramas, etc.
GOOGLE_API_KEY=tu_clave_aqui

# Opcional: modelo Gemini (default en código: gemini-2.0-flash)
GEMINI_MODEL=gemini-2.0-flash

# Opcional: PostgreSQL/Supabase. Sin esta variable, Nura usa SQLite (db/nura.db)
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Opcional — bot de Telegram (webhook)
TELEGRAM_TOKEN=
WEBHOOK_URL=https://tu-dominio.com/webhook
# PORT=8000   # puerto de uvicorn para bot/main.py (default 8000)
```

```bash
# 4. Lanzar la app web
streamlit run ui/app.py
```

La aplicación queda disponible en `http://localhost:8501`.

### Bot de Telegram (opcional)

Con `TELEGRAM_TOKEN` y `WEBHOOK_URL` definidos, podés servir el webhook:

```bash
python -m uvicorn bot.main:app --host 0.0.0.0 --port 8000
# o: python bot/main.py
```

La URL pública debe coincidir con la ruta que registrás en Telegram. Ver comentarios en `bot/main.py` para el flujo anti-timeout del webhook.

---

## Base de datos dual

Nura selecciona el motor automáticamente según el entorno:

| Situación | Motor | Cuándo |
|-----------|--------|--------|
| `DATABASE_URL` en `.env` | PostgreSQL (Supabase) | Producción / multi-dispositivo |
| Sin `DATABASE_URL` | SQLite (`db/nura.db`) | Desarrollo local y tests |

El esquema y las operaciones CRUD son idénticos en ambos motores salvo detalles internos de placeholders. Al conectar a Supabase por primera vez, `init_db()` crea las tablas necesarias (incluidas jerarquía, vinculación Telegram, sesiones de examen, etc.).

---

## Uso

### Vistas principales

**Descubrir** — Chat de captura y tutor:

- Escribe un término (`tasa de interés`) → Nura lo guarda, clasifica, conecta y puede inferir jerarquía.
- Saludos o frases cortas → modo **chat** (respuesta breve del tutor sin tocar la BD).
- Pregunta con `?` o interrogativas → el tutor responde con contexto y herramientas.
- Nura detecta términos técnicos nuevos en la respuesta y te ofrece guardarlos.
- Corrección ortográfica y desambiguación cuando aplica.

**Dominar** — Repaso, quiz y examen:

- Flashcards con SM-2 y conceptos debidos hoy.
- Quiz por palabras clave desde el chat principal.
- **Examen** por categoría desde la UI (y `/examen` en Telegram).

**Conectar** — Mapa de conocimiento:

- Grafo pyvis, filtros por categoría y nivel de dominio, edición desde tarjetas.

---

## Arquitectura del pipeline

```
Usuario escribe input
        │
   capture_agent     ← heurísticas + spell-check / clarify (Gemini) cuando aplica
        │
        ├─ chat / question ──→ tutor ─────────────────────────────→ END
        ├─ capture / reclassify ──→ [websearch_node?] ──→ classifier ──→ connector ──→ END
        ├─ review      ──→ review ───────────────────────────────→ END
        ├─ quiz        ──→ quiz ──────────────────────────────────→ END
        ├─ insight     ──→ insight ─────────────────────────────────→ END
        └─ clarify / spelling / confirm_reclassify ──→ END (la UI continúa el flujo)
```

- **`websearch_node`**: enriquece el concepto con resultados web y sigue a `classifier` → `connector`.
- Tras **`connector`**, la capa de aplicación puede invocar **`hierarchy_agent`** para guardar relaciones en `concept_hierarchy` (no es un nodo separado del mismo `StateGraph`).

---

## Tests

```bash
# Ejecutar todos los tests (en CI suele forzarse DATABASE_URL vacía vía conftest)
python -m pytest tests/ -v --tb=short -q
```

Los tests usan SQLite en memoria o temporales; no deben tocar la BD de producción. El conteo de tests crece con los sprints (del orden de **~363** al momento de escribir este README).

---

## Modelo de datos (resumen)

```
User
  id, username, password_hash, created_at,
  profession, learning_area, tech_level,
  daily_goal, reminder_time,
  telegram_id, link_code, link_code_expiry,
  last_tutor_response

Concept  (UNIQUE: term + user_id)
  … mastery_level, SM-2, is_classified, user_context, user_id → User

Connection
  concept_id_a, concept_id_b, relationship, user_id → User

concept_hierarchy (tabla)
  user_id, child_concept_id, parent_concept_id, relation_type

DailySummary  (UNIQUE: date + user_id)
  concepts_captured, new_connections, concepts_reviewed, …
```

---

## Variables de entorno

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `GOOGLE_API_KEY` | Sí (app completa) | Google AI Studio |
| `GEMINI_MODEL` | No | Modelo Gemini |
| `DATABASE_URL` | No | PostgreSQL; sin ella → SQLite |
| `TELEGRAM_TOKEN` | No | Bot de Telegram |
| `WEBHOOK_URL` | No | URL pública del webhook |
| `PORT` | No | Puerto del servidor FastAPI del bot (default 8000) |

> **Cuotas Gemini:** el plan gratuito tiene límites de requests/minuto. Si los agentes fallan, esperá unos segundos o probá otro modelo en `GEMINI_MODEL`.

---

## Decisiones de diseño

- **Base de datos dual**: SQLite para desarrollo/tests, PostgreSQL para producción; placeholders y `lastrowid`/`RETURNING` abstractos en la capa de conexión.
- **Sin ORM**: `sqlite3` / `psycopg2` explícitos.
- **Dataclasses `frozen=True`**: objetos de dominio inmutables donde aplica.
- **Multi-usuario**: `user_id` en conceptos, conexiones, resúmenes y jerarquía.
- **SM-2**: intervalo y factor de facilidad por concepto.
- **Perfil de usuario**: inyectado en prompts de clasificación y tutor.
- **Timeout** razonable en invocaciones al grafo desde la UI para no colgar Streamlit.
- **`ClassificationError`**: fallos de API dejan el concepto con `is_classified=False` para reintento.
- **Streamlit `st.cache_resource`**: el grafo LangGraph se construye una vez por proceso.
- **Webhook Telegram**: respuesta HTTP inmediata y procesamiento en segundo plano para evitar reintentos en bucle por timeout de Telegram.
