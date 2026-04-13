Sprint 6 completo. Resultado: 5/5 passed.

Resumen del Sprint 6
db/operations.py — nueva función
get_concept_connections_detail(concept_id) — resuelve cada conexión hacia el Concept del otro extremo y devuelve list[dict] con {'concept': Concept, 'relationship': str}. Usa la ya existente get_connections_for_concept internamente.

ui/components.py — dos cambios
render_knowledge_map(concepts, connections, filter_categories=None, filter_min_mastery=0) — los dos nuevos parámetros filtran la lista de visible antes de construir el grafo pyvis. Los nodos que no cumplan ambos criterios (categoría y mastery mínimo) desaparecen del mapa junto con sus aristas.

render_concept_detail_panel(concept, connections_detail) — nuevo componente que muestra:

Cabecera con nombre, categoría y subcategoría
Explicación completa
Para cada conexión: frase legible "TERM se conecta con OTHER — descripción de la relación"
Mensaje vacío amigable si no hay conexiones
ui/app.py — sección del mapa renovada
Dentro del expander 🔍 Filtros del mapa:

multiselect de categorías disponibles (calculadas dinámicamente desde la BD)
slider de dominio mínimo 0–5
Debajo del mapa:

Selectbox 🔎 Explorar concepto que lista solo los conceptos visibles tras los filtros
Al seleccionar uno, llama a get_concept_connections_detail y renderiza render_concept_detail_panel con todos sus vínculos explicados


Ctrl+K to generate command
