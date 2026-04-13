# Sprint 16 — Mensaje motivador híbrido

## Objetivo
Mostrar un mensaje motivador personalizado al final 
de cada sesión de aprendizaje, usando lógica híbrida:
determinista para seleccionar el tipo de mensaje,
generativo para redactarlo.

## Lógica de selección (determinista)
El código detecta el evento más relevante de la sesión:

1. Primera sesión → mensaje de bienvenida especial
2. Racha >= 7 días → celebración de consistencia
3. Conexiones nuevas > 3 → énfasis en conexiones
4. Conceptos nuevos > 5 → énfasis en crecimiento
5. Solo repasó → énfasis en consolidación
6. Quiz con score < 60% → mensaje de aliento
7. Default → mensaje motivador general

## Generación del mensaje (Gemini)
Gemini recibe: tipo de evento + datos reales de la sesión
+ metáfora de constelación/conocimiento conectado.
Genera máximo 2 líneas, tono cercano y motivador.
Nunca el mismo mensaje dos veces.

## Cuándo mostrar
Al cerrar sesión O después de completar una sesión 
de flashcards/quiz. Banner sutil en la parte inferior
de la vista Dominar.

## Harness
- Lógica determinista selecciona tipo correcto
- Gemini genera mensaje no vacío
- Mensaje incluye metáfora de constelación
- No muestra si no hubo actividad en la sesión
- Fallo de API muestra mensaje determinista de respaldo