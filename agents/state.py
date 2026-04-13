"""
agents/state.py
===============
Definición del estado compartido que fluye a través del grafo LangGraph de Nura.

NuraState es un TypedDict: un diccionario con tipos estáticos que LangGraph
usa como contrato entre nodos.  Cada nodo recibe el estado completo, realiza
su trabajo y devuelve un diccionario parcial con solo los campos que modificó.
LangGraph fusiona esa actualización parcial con el estado anterior automáticamente.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from db.models import Concept, Connection


class NuraState(TypedDict):
    """
    Estado global del pipeline de captura y clasificación de Nura.

    Campos
    ------
    user_input       : Texto crudo que el usuario envió al sistema.
    user_context     : Contexto adicional opcional (p. ej. "leído en libro X").
                       Vacío si el usuario no proporcionó contexto extra.
    current_concept  : Concepto que se está procesando en este ciclo.
                       None al inicio o cuando el input es una pregunta.
    all_concepts     : Snapshot de todos los conceptos en la BD al momento
                       de la captura.  El conector lo usa para buscar relaciones
                       sin hacer consultas repetidas a la base de datos.
    new_connections  : Conexiones creadas durante este ciclo de procesamiento.
                       Lista vacía si no se encontraron relaciones.
    response         : Mensaje de texto que el sistema devuelve al usuario
                       al final del pipeline.
    mode             : Modo de operación detectado por capture_agent.
                       'chat'               — expresión conversacional corta (saludo,
                                              confirmación, "no entiendo", "ayuda"…).
                                              El tutor responde sin consultar BD ni web.
                       'capture'            — el input es un término nuevo a aprender.
                       'question'           — el input es una pregunta al tutor.
                       'review'             — el usuario solicita repasar conceptos.
                       'reclassify'         — término existente sin clasificar:
                                              ir directo a classifier sin save_concept.
                       'confirm_reclassify' — término ya clasificado que el usuario
                                              volvió a escribir (Sprint 20).  La UI muestra
                                              un banner preguntando si es el mismo concepto
                                              o uno diferente; el usuario elige entre
                                              actualizar contexto (→ reclassify) o buscar
                                              en web (→ websearch_classify).
                       'quiz'               — el usuario solicita un quiz de opción múltiple.
                       'insight'            — modo especial: no viene del usuario sino de la UI
                                              al inicio de la sesión diaria.  insight_agent
                                              genera un mensaje personalizado basado en patrones.
    user_id          : ID del usuario autenticado.  Todos los agentes lo pasan a las
                       funciones de operations.py para aislar los datos por usuario.
                       Valor por defecto 1 para compatibilidad con tests anteriores.
    quiz_questions   : Lista de preguntas generadas por quiz_agent.  Cada dict tiene:
                       concept_id (int), question (str), options (list[str] x4),
                       correct_index (int 0-3), explanation (str).
                       Lista vacía en todos los modos que no sean 'quiz'.
    sources          : Fuentes web consultadas por tutor_agent (Sprint 10).  Cada dict tiene:
                       title (str), url (str), snippet (str).
                       Lista vacía si tutor_agent respondio sin web search.
    insight_message  : Mensaje generado por insight_agent (Sprint 12).  Se guarda
                       separado de 'response' para que la UI pueda mostrarlo en un
                       banner especial sin confundirlo con respuestas del tutor.
                       Cadena vacía en todos los modos que no sean 'insight'.
    clarification_options : Sprint 14.  Lista de 2-3 significados posibles para el
                       término cuando mode='clarify'.  La UI los muestra como botones
                       para que el usuario elija cuál quiso decir antes de clasificar.
                       Lista vacía en todos los modos que no sean 'clarify'.
    spelling_suggestion   : Sprint 14.  Término corregido sugerido por el detector de
                       ortografía cuando mode='spelling'.  La UI muestra "¿Quisiste
                       decir X?" con botones Sí/No.  Cadena vacía en otros modos.
    user_profile          : Sprint 15.  Perfil del usuario completado durante el
                       onboarding.  Dict con keys: profession (str), learning_area (str),
                       tech_level (str).  Los agentes de clasificación y tutoría lo usan
                       para personalizar sus prompts y ejemplos.
                       Dict vacío si el usuario no ha completado el onboarding.
    diagram_svg           : Sprint 17.  SVG generado por diagram_tool para ilustrar la
                       respuesta del tutor.  Cadena vacía en todos los modos que no
                       sean 'question', o cuando el diagrama no fue necesario o falló.
    suggested_concepts    : Sprint 18.  Conceptos técnicos detectados en la respuesta
                       del tutor que el usuario aún no tiene en su mapa.  La UI los
                       muestra como sugerencias para agregar con un solo click.
                       Lista vacía en todos los modos que no sean 'question', o
                       cuando la detección no encontró conceptos nuevos.
    """

    user_input: str
    user_context: str          # Sprint 5: contexto opcional ingresado por el usuario
    current_concept: Optional[Concept]
    all_concepts: list[Concept]
    new_connections: list[Connection]
    response: str
    mode: str  # 'chat'|'capture'|'question'|'review'|'reclassify'|'confirm_reclassify'|'quiz'|'insight'|'clarify'|'spelling'|'websearch_classify'
    user_id: int                # Sprint 11: ID del usuario autenticado (default=1)
    quiz_questions: list[dict]  # Sprint 9: preguntas generadas por quiz_agent; vacío si no es modo quiz
    sources: list[dict]         # Sprint 10: fuentes web usadas por tutor_agent; vacío si no hubo web search
    insight_message: str        # Sprint 12: mensaje del insight_agent; vacío si no es modo insight
    clarification_options: list[str]  # Sprint 14: significados posibles para mode='clarify'
    spelling_suggestion: str          # Sprint 14: corrección sugerida para mode='spelling'
    user_profile: dict                # Sprint 15: perfil del usuario {profession, learning_area, tech_level}
    diagram_svg: str                  # Sprint 17: SVG del diagrama generado por tutor_agent; vacío si no aplica
    suggested_concepts: list[str]    # Sprint 18: conceptos nuevos detectados en la respuesta del tutor
