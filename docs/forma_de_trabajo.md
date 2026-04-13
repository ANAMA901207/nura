# Forma de Trabajo — Nura

## Metodología: HDD (Harness-Driven Development)

### Principios fundamentales
1. **Specs primero** — antes de escribir código, documentar 
   qué se va a construir en `docs/sprintN_spec.md`
2. **Harnesses antes que código** — los tests definen 
   el comportamiento esperado antes de implementar
3. **No romper lo que funciona** — cada sprint debe pasar 
   todos los tests anteriores + los nuevos
4. **Cierre formal** — cada sprint termina con 
   `docs/sprintN_close.md` con el reporte completo

### Reglas de oro
- **NUNCA** modificar archivos existentes sin entender 
  su impacto en el resto del sistema
- **SIEMPRE** correr `python -m pytest tests/ -v` antes 
  de declarar un sprint cerrado
- **SIEMPRE** agregar migraciones idempotentes para 
  cambios de BD — nunca asumir BD limpia
- **SIEMPRE** manejar errores de API con mensajes 
  amigables — nunca mostrar tracebacks al usuario
- **NUNCA** hardcodear API keys — siempre usar `.env`
- **SIEMPRE** usar queries parametrizadas — nunca f-strings 
  en SQL

### Estructura de carpetas

nura/
├── agents/      # Nodos LangGraph
├── tools/       # Funciones que llaman APIs externas
├── db/          # Models, schema, operations
├── ui/          # Streamlit app y componentes
├── tests/       # Harnesses por sprint
└── docs/        # Specs, closes y forma de trabajo

### Formato de cada sprint
1. Crear `docs/sprintN_spec.md` con objetivo y harness
2. Dar prompt a Cursor con instrucciones completas
3. Cursor construye y corre harness
4. Cuando el harness pase, Cursor crea automáticamente `docs/sprintN_close.md`
   con el resumen completo de lo que se construyó, los archivos modificados y
   el resultado del harness. El humano no necesita crearlo manualmente.
5. Si fallan → corregir antes de continuar
6. Correr suite completo: `python -m pytest tests/ -v`
7. Push a GitHub

> **Regla general:** Al finalizar cualquier sprint o fix, Cursor siempre crea
> o actualiza el documento de cierre correspondiente antes de reportar los
> passed.

### Stack
- Python 3.14
- LangGraph 1.1.4
- langchain-google-genai (Gemini 2.5 Flash)
- Streamlit
- SQLite (pyvis para mapa visual)
- bcrypt para auth

### Variables de entorno (.env)

GOOGLE_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash

### Convenciones de naming
- Agentes: `nombre_agent.py` en `/agents`
- Tools: `nombre_tool.py` en `/tools`
- Tests: `test_sprintN.py` en `/tests`
- Docs: `sprintN_spec.md` y `sprintN_close.md` en `/docs`

## Estructura de carpetas obligatoria

```
nura/
├── agents/      # Nodos LangGraph
├── db/          # Models, schema, operations, nura.db
├── design/      # Referencias de diseño (v0, mockups)
├── docs/        # Specs, closes, forma_de_trabajo
├── tests/       # Harnesses por sprint
├── tools/       # Tools que llaman APIs externas
└── ui/          # Streamlit app, components, auth
```

**Regla:** nunca crear carpetas fuera de esta estructura sin documentarlo aquí primero.

