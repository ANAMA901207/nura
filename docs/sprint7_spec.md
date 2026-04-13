# Sprint 7 — Flashcards inteligentes + Dominio real

## Objetivo
Hacer las flashcards interactivas con aciertos/errores
y calcular el dominio real basado en rendimiento.

## Lógica de dominio
- 0 ☆☆☆☆☆ — recién capturado
- 1 ★☆☆☆☆ — visto 1 vez
- 2 ★★☆☆☆ — 1 acierto
- 3 ★★★☆☆ — 3 aciertos consecutivos
- 4 ★★★★☆ — 5 aciertos consecutivos
- 5 ★★★★★ — dominado (SM-2 lo marca estable)

## Funcionalidades
1. Botones ✅ Lo sabía / ❌ No lo sabía en cada flashcard
2. Acierto → sube mastery, programa próximo repaso
3. Error → baja mastery, flashcard vuelve a la cola
4. Flashcard se repite hasta 3 aciertos consecutivos en sesión
5. Al terminar sesión: resumen con aciertos, errores, 
   conceptos dominados nuevos

## Harness
- Acierto actualiza mastery_level correctamente
- Error no sube mastery y reagenda la flashcard
- Flashcard con 3 errores consecutivos baja mastery
- Sesión termina cuando todos tienen 1+ acierto
- Resumen final muestra conteos correctos