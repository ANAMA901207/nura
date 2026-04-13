# Sprint 18 — Tutor detecta conceptos nuevos y sugiere agregarlos

## Objetivo
Cuando el tutor responde una pregunta, detectar automáticamente
los conceptos mencionados en la respuesta y ofrecer al usuario
agregarlos a su mapa de conocimiento.

## Flujo
1. Usuario pregunta: "¿cuál es la diferencia entre IA y ML?"
2. Tutor responde con explicación
3. Nura detecta conceptos mencionados: ["IA", "Machine Learning",
   "algoritmos", "datos de entrenamiento"]
4. Filtra los que el usuario YA tiene en su BD
5. Muestra sugerencia: "Encontré estos conceptos nuevos en mi
   respuesta — ¿quieres agregarlos a tu mapa?"
6. Usuario selecciona cuáles agregar con checkboxes
7. Los seleccionados se clasifican y guardan automáticamente

## Reglas de detección
- Solo conceptos técnicos o de negocio (no artículos ni verbos)
- Mínimo 2 caracteres, máximo 4 palabras
- Excluir conceptos que el usuario ya tiene
- Máximo 5 sugerencias por respuesta

## UI
- Banner sutil debajo de la respuesta del tutor
- Checkboxes para seleccionar cuáles agregar
- Botón "Agregar seleccionados"
- Si el usuario ignora, no vuelve a preguntar por esa respuesta

## Harness
- Detección retorna lista de términos técnicos
- Filtrado excluye conceptos ya en BD del usuario
- Selección y guardado funciona correctamente
- Respuesta sin conceptos nuevos no muestra sugerencia
- Máximo 5 sugerencias por respuesta