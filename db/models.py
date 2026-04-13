"""
db/models.py
============
Definiciones de los modelos de datos de Nura como dataclasses inmutables.

Cada clase representa una tabla en la base de datos SQLite y se usa como
el tipo de retorno de todas las funciones en operations.py.  Al ser frozen=True,
las instancias no pueden modificarse una vez creadas, lo que evita mutaciones
accidentales fuera de la capa de base de datos.

Sprint 11: se agrega la clase User y se añade user_id a Concept, Connection
y DailySummary para soportar múltiples usuarios con datos aislados.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional


@dataclass(frozen=True)
class Concept:
    """
    Representa un concepto capturado por el sistema de aprendizaje.

    Un concepto es la unidad mínima de conocimiento en Nura.  Se crea
    cuando el usuario encuentra un término nuevo y puede enriquecerse
    progresivamente con explicación, ejemplos y analogías.

    Campos
    ------
    id              : Clave primaria autoincremental asignada por SQLite.
    term            : El término o palabra clave del concepto (único en la BD).
    category        : Categoría temática amplia, p. ej. "filosofía", "biología".
    subcategory     : Subcategoría más específica dentro de la categoría.
    explanation     : Definición o explicación del concepto.
    examples        : Ejemplos concretos que ilustran el concepto.
    analogy         : Analogía para facilitar la comprensión intuitiva.
    context         : Fuente o situación donde apareció el término (libro, clase…).
    flashcard_front : Pregunta que aparece al frente de la flashcard.
    flashcard_back  : Respuesta que aparece al dorso de la flashcard.
    mastery_level   : Nivel de dominio del concepto, de 0 (nuevo) a 5 (dominado).
    created_at      : Marca de tiempo de creación del concepto.
    last_reviewed   : Última vez que se revisó; None si nunca se ha repasado.
    is_classified        : True cuando el clasificador ya enriqueció el concepto con
                           categoría, explicación y flashcards.  False si la clasificación
                           aún no se ejecutó (p. ej. por cuota de API agotada).
    user_context         : Contexto opcional ingresado por el usuario al capturar el término
                           (p. ej. "leído en el libro X").  Vacío si no se proporcionó.
    consecutive_correct  : Contador de aciertos seguidos en las flashcards.
                           Se resetea a 0 en cuanto hay un error.
    consecutive_incorrect: Contador de errores seguidos.  Se resetea a 0 con un acierto.
    total_reviews        : Número total de veces que se ha evaluado la flashcard
                           (suma de aciertos y errores históricos).
    next_review          : Próxima fecha sugerida de repaso calculada por record_flashcard_result.
                           None si el concepto nunca se ha repasado con el nuevo sistema.
    sm2_interval         : Número de días hasta el próximo repaso según SM-2.
                           Empieza en 1.0 y crece multiplicando por sm2_ef tras cada acierto.
    sm2_ef               : Factor de facilidad del algoritmo SM-2.  Valor inicial 2.5.
                           Sube ligeramente con aciertos, baja 0.2 con errores, mínimo 1.3.
    """

    id: int
    term: str
    category: str
    subcategory: str
    explanation: str
    examples: str
    analogy: str
    context: str
    flashcard_front: str
    flashcard_back: str
    mastery_level: int  # 0 = nunca visto, 5 = completamente dominado
    created_at: datetime
    last_reviewed: Optional[datetime]  # None hasta el primer repaso
    # Sprint 5: clasificación diferida y contexto del usuario
    is_classified: bool = False   # True después de que el clasificador enriqueció el concepto
    user_context: str = ""        # Contexto opcional que el usuario proporcionó al capturar
    # Sprint 7: métricas de rendimiento para el sistema de dominio inteligente
    consecutive_correct: int = 0       # Aciertos consecutivos sin ningún error intermedio
    consecutive_incorrect: int = 0     # Errores consecutivos sin ningún acierto intermedio
    total_reviews: int = 0             # Total de veces que se ha revisado esta flashcard
    next_review: Optional[datetime] = None  # Próxima fecha programada de repaso; None = sin programar
    # Sprint 8: parámetros del algoritmo SM-2 (Spaced Repetition)
    sm2_interval: float = 1.0  # Intervalo actual en días hasta el próximo repaso programado
    sm2_ef: float = 2.5        # Factor de facilidad (Easiness Factor); nunca baja de 1.3
    # Sprint 11: propietario del concepto — 1 = usuario por defecto / legacy
    user_id: int = 1


@dataclass(frozen=True)
class Connection:
    """
    Representa un vínculo semántico entre dos conceptos.

    Las conexiones permiten construir un grafo de conocimiento donde
    los nodos son Concepts y las aristas son Connections.  La relación
    es direccional en la BD (a → b), pero las consultas la tratan como
    bidireccional al recuperar conexiones por cualquiera de los dos IDs.

    Campos
    ------
    id            : Clave primaria autoincremental.
    concept_id_a  : ID del primer concepto (origen de la relación).
    concept_id_b  : ID del segundo concepto (destino de la relación).
    relationship  : Descripción textual del vínculo, p. ej. "es opuesto a".
    created_at    : Marca de tiempo de creación de la conexión.
    """

    id: int
    concept_id_a: int
    concept_id_b: int
    relationship: str
    created_at: datetime
    # Sprint 11: propietario de la conexión
    user_id: int = 1


@dataclass(frozen=True)
class DailySummary:
    """
    Agrega las métricas de actividad de aprendizaje de un día concreto.

    Se crea automáticamente la primera vez que se consulta una fecha y
    se actualiza a medida que el usuario captura conceptos, forma conexiones
    o repasa material durante esa jornada.

    Campos
    ------
    id                 : Clave primaria autoincremental.
    date               : Fecha a la que pertenece el resumen (única en la BD).
    concepts_captured  : Número de conceptos nuevos guardados ese día.
    new_connections    : Número de conexiones nuevas creadas ese día.
    concepts_reviewed  : Número de conceptos repasados (flashcards) ese día.
    """

    id: int
    date: date
    concepts_captured: int
    new_connections: int
    concepts_reviewed: int
    # Sprint 11: propietario del resumen diario
    user_id: int = 1


@dataclass(frozen=True)
class User:
    """
    Representa una cuenta de usuario registrada en Nura.

    La contraseña NUNCA se almacena en texto plano: el campo password_hash
    guarda el hash bcrypt generado por create_user().  La verificación se
    realiza con bcrypt.checkpw() en authenticate_user().

    Campos
    ------
    id            : Clave primaria autoincremental asignada por SQLite.
    username      : Nombre de usuario único (case-sensitive en la BD).
    password_hash : Hash bcrypt de la contraseña; comienza con '$2b$'.
    created_at    : Marca de tiempo de registro de la cuenta.
    profession    : Sprint 15. Perfil profesional del usuario elegido durante
                    el onboarding (p. ej. "Analista de crédito/banca").
                    Cadena vacía si el onboarding aún no se completó.
    learning_area : Sprint 15. Área de interés del usuario elegida durante
                    el onboarding (p. ej. "Finanzas y negocios").
                    Cadena vacía si el onboarding aún no se completó.
    tech_level    : Sprint 15. Nivel de experiencia del usuario elegido durante
                    el onboarding (p. ej. "Intermedio").
                    Cadena vacía si el onboarding aún no se completó.
    """

    id: int
    username: str
    password_hash: str
    created_at: datetime
    # Sprint 15: perfil de onboarding — adaptan los prompts de clasificación y tutor
    profession:    str = ""
    learning_area: str = ""
    tech_level:    str = ""
