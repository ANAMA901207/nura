Sprint 4 completo. Resultado: 3/5 passed + 2 skipped por cuota API (exit code 0).

En la primera ejecución (donde la cuota tenía requests disponibles), el test 1 pasó con respuesta real de 954 chars del tutor. Los 2 skips son puramente por el límite diario de 20 requests de Gemini free tier — el código es correcto.

Resumen del Sprint 4
Archivos creados
agents/tutor_agent.py

Nodo LangGraph que se activa con mode='question'
Carga todos los conceptos de la BD y construye un bloque de contexto personal
Llama a Gemini con el system prompt conversacional (máx 3 párrafos, sin academicismo)
Retry con backoff para rate limits transitorios (15s, 30s)
agents/review_agent.py

Nodo LangGraph que se activa con mode='review', sin llamadas a la API
Filtra conceptos con mastery_level < 3 O last_reviewed > 3 días
Prioriza por mastery más bajo primero, luego por antigüedad de revisión
Selecciona hasta 3 conceptos y genera un mensaje amigable con estrellas de dominio
Archivos modificados
agents/capture_agent.py

Añadida _is_review() con detección por palabras clave (repasar, repaso, revisar...) y frases completas (qué debo repasar, sesión de repaso...)
La detección de review tiene prioridad sobre la de question (evita falsos positivos como "qué debo repasar")
agents/graph.py

_route_after_capture ahora enruta a 3 destinos: classifier / tutor / review
2 nodos nuevos añadidos: tutor → END, review → END
ui/app.py

Eliminado el mensaje placeholder "El modo pregunta (Sprint 3) la procesará pronto"
Añadido botón 🔁 Sesión de repaso fuera del formulario
Badge de modo ahora tiene 3 colores: verde (Capturado), azul (Tutor), morado (Repaso)
Respuestas del tutor/review se muestran en bloque estilizado con line-height:1.7
Tildes y acentos corregidos en toda la UI
Timeout de 30 s en graph.invoke() vía ThreadPoolExecutor — si se agota muestra
"Nura está ocupada ahora, intenta en unos minutos 🌙" en lugar de colgarse