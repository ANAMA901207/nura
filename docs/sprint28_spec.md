# Sprint 28 — Árbol jerárquico conceptual

## Objetivo
Darle al usuario el "mapa completo" — no solo conexiones
entre conceptos sino la estructura jerárquica de lo que
está aprendiendo. Responde la pregunta:
"¿Dónde encaja esto en el universo de lo que sé?"

## El problema que resuelve
Hoy el mapa de nodos muestra conexiones (A se relaciona
con B) pero no jerarquía (A contiene a B, B es subtipo
de A). El usuario tiene que construir ese árbol mental
solo — Nura lo hace automáticamente.

## Ejemplo
Inteligencia Artificial
├── Machine Learning
│   ├── Supervisado
│   ├── No supervisado
│   └── Por refuerzo
│       └── Deep Learning
│           └── Transformers
│               └── LLMs
└── IA simbólica

## Funcionalidades

### 1. Detección de jerarquía al capturar
Cuando el usuario captura un concepto nuevo, Nura
detecta automáticamente:
- ¿Este concepto es subtipo de alguno que ya tienes?
- ¿Este concepto contiene a alguno que ya tienes?
- La relación (es_tipo_de, contiene, es_parte_de)

### 2. Vista "Árbol" en Conectar
Nueva pestaña o toggle en la vista Conectar:
- Vista actual: mapa de nodos (conexiones)
- Vista nueva: árbol jerárquico colapsable
- El árbol muestra los conceptos organizados por
  categoría y jerarquía
- Click en un nodo → explicación de por qué está
  ahí y cómo se relaciona con su padre e hijos

### 3. Comando Telegram /arbol [categoría]
- `/arbol` → árbol completo en texto ASCII
- `/arbol IA` → árbol solo de la categoría IA

## Archivos a modificar
- `db/schema.py` — nueva tabla `concept_hierarchy`:
  (id, user_id, child_id, parent_id, relation_type,
  created_at)
- `db/operations.py` — funciones:
  `save_hierarchy(user_id, child_id, parent_id,
  relation_type)`
  `get_hierarchy(user_id) -> list`
  `get_concept_tree(user_id, category=None) -> dict`
- `agents/hierarchy_agent.py` — nuevo agente:
  `detect_hierarchy(new_concept, existing_concepts,
  user_profile) -> list[HierarchyRelation]`
- `agents/capture_agent.py` — después de clasificar,
  llamar al hierarchy_agent
- `ui/app.py` — toggle árbol/mapa en vista Conectar
- `ui/components.py` — `render_tree(tree_dict)`
- `bot/handlers.py` — comando `/arbol [categoría]`

## Harness
- `test_hierarchy_table_exists`
- `test_save_and_get_hierarchy`
- `test_get_concept_tree_structure`
- `test_hierarchy_agent_detects_parent`
- `test_hierarchy_agent_detects_child`
- `test_arbol_command_returns_text`
- `test_arbol_with_category_filters`

## Reglas
- El hierarchy_agent nunca bloquea la captura —
  si falla, el concepto se guarda igual
- No romper tests existentes
- Correr pytest al cerrar y crear sprint28_close.md