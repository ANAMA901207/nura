# Sprint 10 — Tutor con Web Search (Cerrado)

## Resultado: 5/5 tests pasados

## Que se construyo

### tools/search_tool.py (nuevo)
- Dependencia: `ddgs` (DuckDuckGo Search, libre y sin API key)
- Funcion `web_search(query, max_results=5) -> dict`:
  - Usa `DDGS` importado a nivel de modulo (permite mocking en tests)
  - Exito: `{"results": [{"title", "url", "snippet"}, ...]}`
  - Error: `{"results": [], "error": str}` — sin propagar excepciones

### agents/state.py
- Nuevo campo `sources: list[dict]` en NuraState
- Cada item: `{title, url, snippet}` — fuentes web usadas por el tutor
- Lista vacia cuando el tutor no realizo busqueda web

### agents/tutor_agent.py
- Dos nuevos prompts:
  - `CLASSIFY_SYSTEM_PROMPT`: pide JSON `{needs_search: bool}` al LLM
  - `TUTOR_SYSTEM_PROMPT`: actualizado para mencionar web search y fuentes
- Helper `_classify_needs_search` extraido en `_parse_needs_search(raw) -> bool`
- Helper `_call_gemini(llm, messages, retries)`: centraliza invocacion con retry
- Helper `_build_search_context(results) -> str`: formatea snippets para el prompt
- Flujo del nodo `tutor_agent`:
  1. Llama a Gemini con CLASSIFY_SYSTEM_PROMPT (temperatura 0.3) para detectar needs_search
  2. Si needs_search=True: llama a web_search(), agrega contexto al prompt, guarda sources
  3. Si web_search falla o devuelve vacio: continua sin fuentes (fallback a BD)
  4. Llama a Gemini con TUTOR_SYSTEM_PROMPT (temperatura 0.7) con contexto BD + web
  5. Devuelve `{response, sources}` al estado

### ui/components.py
- Nueva funcion `render_sources(sources: list[dict]) -> None`:
  - No-op si la lista esta vacia
  - Muestra encabezado "Fuentes consultadas" en gris
  - Cada fuente: link clicable azul con snippet debajo (120 chars max)
  - Estilo: borde izquierdo azul, fondo oscuro sutil

### ui/app.py
- Import: `render_sources`
- `_empty_state`: incluye `sources: []`
- `_TIMEOUT_RESULT`: incluye `quiz_questions: []` y `sources: []`
- Historia Tab 1 — rama `else` (tutor/review):
  - Badge `🌐 Consultando fuentes actualizadas` (azul) si `mode=question` y `sources` no vacio
  - Llama a `render_sources(sources)` despues de la respuesta si hay fuentes

### tests/test_sprint10.py
- 5 verificaciones:
  1. Pregunta de version de herramienta → needs_search=True (API Gemini)
  2. Pregunta conceptual → needs_search=False (API Gemini)
  3. web_search con query valida → dict con campo results y estructura correcta
  4. Fallo simulado de DDGS → dict `{results: [], error: str}` sin excepcion (mock)
  5. Tutor con web_search vacio → responde con BD, sources=[] (mock completo)
