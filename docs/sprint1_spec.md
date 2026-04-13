# Sprint 1 — Base de datos + Modelos de datos

## Objetivo
Construir la capa de persistencia completa de Nura con tests que verifiquen 
cada operación antes de tocar agentes o UI.

## Archivos a crear
- `db/schema.py` — definición de tablas SQLite
- `db/models.py` — dataclasses de los modelos
- `db/operations.py` — funciones CRUD
- `tests/test_db.py` — harness completo

## Modelos

### Concept
- id (int, autoincrement)
- term (str)
- category (str)
- subcategory (str)
- explanation (str)
- examples (str)
- analogy (str)
- context (str) — dónde apareció el término
- flashcard_front (str)
- flashcard_back (str)
- mastery_level (int, 0-5)
- created_at (datetime)
- last_reviewed (datetime, nullable)

### Connection
- id (int, autoincrement)
- concept_id_a (int, FK)
- concept_id_b (int, FK)
- relationship (str) — descripción de la relación
- created_at (datetime)

### DailySummary
- id (int, autoincrement)
- date (date)
- concepts_captured (int)
- new_connections (int)
- concepts_reviewed (int)

## Operaciones requeridas
- save_concept(term, context) → Concept
- get_all_concepts() → list[Concept]
- get_concept_by_id(id) → Concept
- save_connection(concept_id_a, concept_id_b, relationship) → Connection
- get_connections_for_concept(concept_id) → list[Connection]
- update_mastery_level(concept_id, level) → Concept
- get_or_create_daily_summary(date) → DailySummary
- update_daily_summary(date, **kwargs) → DailySummary

## Harness (criterios de verificación)
- Guardar concepto y recuperarlo por ID → mismo objeto
- Guardar dos conceptos y conectarlos → conexión recuperable por ambos IDs
- Actualizar mastery_level → persiste correctamente
- DailySummary se crea si no existe, se actualiza si existe
- No se pueden guardar dos conceptos con el mismo term
- Conexión entre IDs inexistentes lanza error controlado