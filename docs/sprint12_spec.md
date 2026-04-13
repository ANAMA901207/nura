# Sprint 12 — Tutor Adaptativo Inteligente

## Objetivo
Convertir Nura de tracker pasivo a tutor que detecta 
patrones, identifica debilidades y adapta activamente 
su comportamiento al usuario.

## Funcionalidades

### 1. Motor de análisis de patrones
- Detecta categorías con muchos conceptos pero mastery bajo
- Identifica conceptos fallados más de 3 veces en flashcards
- Detecta temas sin actividad hace más de 7 días
- Analiza hora de mayor actividad del usuario

### 2. Intervenciones proactivas
- Al abrir la app: mensaje personalizado basado en patrones
  Ejemplo: "Hola Ana — llevas 3 días sin repasar Agentes 
  y es tu área más débil. ¿Empezamos por ahí?"
- Después de quiz malo: sugerencia de enfoque diferente
- Después de racha de aciertos: celebración + siguiente reto

### 3. Perfil de aprendizaje dinámico
- Detecta si el usuario aprende más por chat o flashcards
- Detecta categorías de mayor y menor dominio
- Genera insight semanal: "Esta semana aprendiste X, 
  tu área más fuerte es Y, te recomiendo enfocarte en Z"

### 4. Nuevo agente: insight_agent
- Se activa al abrir la app si hay suficiente data (>5 conceptos)
- Analiza la BD del usuario y genera mensaje personalizado
- Máximo 3 líneas, tono amigable y motivador

## Harness
- insight_agent genera mensaje no vacío con >5 conceptos
- insight_agent no falla con BD vacía
- Detección de categoría débil es correcta
- Intervención post-quiz aparece cuando score < 60%
- Perfil dinámico detecta método de aprendizaje preferido