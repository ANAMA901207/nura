Sprint 5 completo. Resultado: 5/5 passed.

Resumen del Sprint 5
Capa de datos
db/models.py — Concept tiene dos campos nuevos con defaults al final del dataclass: is_classified: bool = False (True solo después de clasificación exitosa) y user_context: str = "" (contexto del usuario).

db/schema.py — El CREATE TABLE incluye las columnas nuevas. La función _run_migrations() ejecuta ALTER TABLE ADD COLUMN envuelto en try/except para migrar automáticamente BDs existentes de forma idempotente.

db/operations.py — Cuatro cambios:

_row_to_concept lee is_classified / user_context con fallback para retrocompatibilidad
save_concept(term, context, user_context) — si el término existe con is_classified=False devuelve el existente; si está clasificado, lanza ValueError como antes
get_concept_by_term(term) — nuevo helper que devuelve Concept | None
get_unclassified_concepts() — lista todos los is_classified=False
update_concept_classification(concept_id, data) — persiste campos + marca is_classified=True
Capa de agentes
tools/classifier_tool.py — Clase ClassificationError que envuelve cualquier fallo (cuota, timeout, JSON inválido, clave ausente). El parámetro user_context se añade al prompt como "Contexto adicional del usuario: ...".

agents/state.py — Campo user_context: str añadido al NuraState.

agents/capture_agent.py — Prioridad 3 nueva: si el término existe con is_classified=False → mode='reclassify' sin duplicar el concepto.

agents/classifier_agent.py — try/except ClassificationError: en fallo, devuelve mensaje amigable "... 🌙" sin tocar la BD; en éxito, llama a update_concept_classification().

agents/graph.py — _route_after_capture enruta 'reclassify' al mismo destino que 'capture' (→ classifier).

UI
ui/app.py — Campo "Contexto opcional: ¿dónde escuchaste este término?" debajo del input principal. En Tab 2, sección roja con los conceptos sin clasificar + botón Reintentar por cada uno.

ui/components.py — render_concept_card(concept, show_edit=False): badge rojo ⚠️ Sin clasificar cuando is_classified=False. Con show_edit=True agrega un expander ✏️ Corregir clasificación con campos editables que llaman a update_concept_classification.