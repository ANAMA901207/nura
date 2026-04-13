# Sprint 20 — Bugs críticos + personalización

## Objetivo
Resolver los bugs que afectan funcionalidad core
y personalizar las respuestas según el perfil del usuario.

## Items

### 1. Flashcard loop infinito
- Límite de 3 repeticiones por concepto en una sesión
- Después de 3 errores: mover concepto a "pendiente para mañana"
- Agregar botón "Terminar sesión" visible en todo momento

### 2. Botón "Repasar ahora" no hace nada
- Investigar y corregir el callback

### 3. Click en nodo no filtra el mapa
- Implementar comunicación pyvis → Streamlit via JS
- Click en nodo activa filtro automáticamente

### 4. Diagramas no se muestran
- Verificar que diagram_svg llega a la UI
- Corregir rendering en app.py

### 5. Timeout muy corto
- Aumentar timeout de 25 a 60 segundos
- Mostrar mensaje de progreso mientras espera

### 6. Personalización de ejemplos
- Reemplazar "Ejemplo en banca" hardcodeado
- Adaptar según profession del usuario

### 7. Cursor reclasificado
- Si término ya existe y usuario lo reescribe
  preguntar: ¿Es el mismo concepto o uno diferente?
- Si diferente → activar web search
- Si mismo → reclasificar con nuevo contexto

## Harness
- Flashcard no repite más de 3 veces en sesión
- Botón Repasar ahora inicia sesión correctamente
- Click en nodo filtra el mapa
- Diagrama aparece en respuestas del tutor
- Timeout de 60 segundos
- Ejemplo usa perfil del usuario
- Cursor pregunta antes de reclasificar