Sprint 7 completo. Resultado: 5/5 passed.

Resumen del Sprint 7
Modelo de datos
db/models.py — Concept tiene 4 campos nuevos con defaults (siempre al final del dataclass):

consecutive_correct: int = 0 — racha de aciertos sin error intermedio
consecutive_incorrect: int = 0 — racha de errores sin acierto intermedio
total_reviews: int = 0 — total histórico de revisiones
next_review: Optional[datetime] = None — próxima fecha programada
db/schema.py — columnas añadidas al CREATE TABLE y a _SPRINT7_MIGRATIONS (migración idempotente sobre BDs existentes).

Lógica de dominio
db/operations.py — record_flashcard_result(concept_id, correct) implementa la tabla de umbrales en una sola transacción atómica:

Evento	Resultado
1 acierto consecutivo	mastery ≥ 2, next_review +1 día
3 aciertos consecutivos	mastery ≥ 3, next_review +3 días
5 aciertos consecutivos	mastery ≥ 4, next_review +7 días
3 errores consecutivos	mastery − 1, next_review = ahora
El mastery nunca baja por un acierto ni sube por un error.

UI
ui/app.py — sección Flashcards completamente rediseñada con lógica de cola:

Botón "Iniciar sesión" carga la cola y registra el nivel inicial de cada concepto
Voltear revela el reverso
✅ Lo sabía → llama a record_flashcard_result(True), la tarjeta sale de la cola
❌ No lo sabía → llama a record_flashcard_result(False), la tarjeta va al final
Resumen de sesión muestra aciertos, errores y qué conceptos subieron de nivel con visualización de estrellas antes/después
ui/components.py — render_flashcard muestra 🔥 Racha: N en la esquina inferior cuando consecutive_correct ≥ 2.