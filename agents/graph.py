"""
agents/graph.py
===============
Definicion y compilacion del StateGraph completo de Nura.

El grafo conecta seis nodos con enrutamiento condicional desde 'capture':

    [START]
       |
    capture
       |
       +── mode == 'chat'        ──> tutor ──────────────────────> [END]
       |
       +── mode == 'capture'     ──> classifier ──> connector ──> [END]
       +── mode == 'reclassify'  ──> classifier ──> connector ──> [END]
       |
       +── mode == 'question'    ──> tutor ──────────────────────> [END]
       |
       +── mode == 'review'      ──> review ────────────────────> [END]
       |
       +── mode == 'quiz'        ──> quiz ──────────────────────> [END]

Uso rápido
----------
    from agents.graph import build_graph

    graph = build_graph()

    # Captura un término nuevo
    result = graph.invoke({
        "user_input": "tasa de interes",
        "current_concept": None,
        "all_concepts": [],
        "new_connections": [],
        "response": "",
        "mode": "",
    })
    print(result["current_concept"].category)  # p. ej. "Finanzas"

    # Hace una pregunta al tutor
    result = graph.invoke({..., "user_input": "que es la tasa de interes?"})
    print(result["response"])  # respuesta conversacional del tutor

    # Inicia una sesión de repaso
    result = graph.invoke({..., "user_input": "que debo repasar hoy"})
    print(result["response"])  # lista de conceptos sugeridos
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from agents.capture_agent import capture_agent, websearch_node
from agents.classifier_agent import classifier_agent
from agents.connector_agent import connector_agent
from agents.tutor_agent import tutor_agent
from agents.review_agent import review_agent
from agents.quiz_agent import quiz_agent
from agents.insight_agent import insight_agent
from agents.state import NuraState

# Sprint 19: lista centralizada de tools formales de Nura.
# Se importa aquí después de los agentes para evitar importaciones circulares.
from tools.db_tools import NURA_TOOLS  # noqa: E402


def _route_after_capture(state: NuraState) -> str:
    """
    Función de enrutamiento condicional ejecutada después del nodo 'capture'.

    Lee el campo mode del estado para decidir la siguiente parada del pipeline:
    - 'chat'        → expresión conversacional; va a 'tutor' (fast-path sin BD).
    - 'capture'     → término nuevo; continúa hacia 'classifier'.
    - 'reclassify'  → término existente sin clasificar; va a 'classifier'
                       (misma ruta que 'capture', pero sin re-insertar en BD).
    - 'question'    → el usuario hizo una pregunta; va a 'tutor'.
    - 'review'      → el usuario quiere repasar; va a 'review'.
    - 'quiz'        → el usuario quiere un quiz; va a 'quiz'.
    - 'insight'     → modo especial de inicio de sesión; va a 'insight'.
    - 'clarify'             → término ambiguo (Sprint 14); va directo a END.
    - 'spelling'            → posible error ortográfico (Sprint 14); va directo a END.
    - 'confirm_reclassify'  → término ya clasificado (Sprint 20); va directo a END.
                               La UI muestra banner con opciones: actualizar o buscar en web.
    - 'websearch_classify'  → búsqueda web solicitada; va a 'websearch_node'
                               que llama a search_tool y luego a 'classifier'.
    - cualquier otro valor → END (failsafe).

    Parámetros
    ----------
    state : Estado actual tras ejecutar capture_agent.

    Devuelve
    --------
    Nombre del siguiente nodo o la constante END de LangGraph.
    """
    mode = state.get("mode", "")
    if mode in ("capture", "reclassify"):
        return "classifier"
    if mode in ("question", "chat"):   # 'chat' comparte el nodo tutor
        return "tutor"
    if mode == "review":
        return "review"
    if mode == "quiz":
        return "quiz"
    if mode == "insight":
        return "insight"
    # Sprint 14: clarify y spelling terminan sin clasificar
    # Sprint 20: confirm_reclassify termina sin clasificar
    # (la UI maneja la interacción con el usuario en estos tres casos)
    if mode in ("clarify", "spelling", "confirm_reclassify"):
        return END
    if mode == "websearch_classify":
        return "websearch_node"
    return END


def build_graph():
    """
    Construye y compila el StateGraph completo de Nura (Sprint 4).

    Nodos registrados
    -----------------
    capture    : Detecta modo (termino/pregunta/repaso/quiz) y persiste el concepto si aplica.
    classifier : Enriquece el concepto con categoria, explicacion y flashcards via Gemini.
    connector  : Detecta y persiste conexiones con conceptos previos via Gemini.
    tutor      : Responde preguntas en modo conversacional usando la BD como contexto.
    review     : Genera una sesion de repaso basada en SM-2 (get_concepts_due_today).
    quiz       : Genera preguntas de opcion multiple sobre conceptos del usuario.

    Aristas
    -------
    START  → capture
    capture → classifier  (mode == 'capture')
    capture → tutor       (mode == 'question')
    capture → review      (mode == 'review')
    classifier → connector
    connector  → END
    tutor      → END
    review     → END

    Devuelve
    --------
    CompiledGraph listo para invocar con graph.invoke(estado_inicial).
    """
    workflow = StateGraph(NuraState)

    # Sprint 19: ToolNode con todos los tools formales registrados.
    # Disponible para invocación cuando los agentes emiten tool_calls.
    # El nodo no forma parte del flujo principal actual (no hay aristas
    # hacia él desde los agentes regulares), pero está listo para activarse
    # en una fase de orquestación dinámica futura.
    workflow.add_node("tools", ToolNode(NURA_TOOLS))

    # Registro de todos los nodos
    workflow.add_node("capture", capture_agent)
    workflow.add_node("websearch_node", websearch_node)
    workflow.add_node("classifier", classifier_agent)
    workflow.add_node("connector", connector_agent)
    workflow.add_node("tutor", tutor_agent)
    workflow.add_node("review", review_agent)
    workflow.add_node("quiz", quiz_agent)
    workflow.add_node("insight", insight_agent)

    # Punto de entrada único
    workflow.set_entry_point("capture")

    # Arista condicional desde capture según el modo detectado
    workflow.add_conditional_edges(
        "capture",
        _route_after_capture,
        {
            "classifier":    "classifier",   # mode 'capture' and 'reclassify'
            "tutor":         "tutor",
            "review":        "review",
            "quiz":          "quiz",
            "insight":       "insight",
            "websearch_node":"websearch_node",
            END:             END,
        },
    )

    # websearch_node enriquece el concepto con snippets web y devuelve
    # mode='capture', por lo que se conecta directamente al pipeline
    # de clasificación estándar: classifier → connector → END.
    workflow.add_edge("websearch_node", "classifier")

    # Pipeline de captura: clasificar → conectar → fin
    workflow.add_edge("classifier", "connector")
    workflow.add_edge("connector", END)

    # Pipelines de un solo nodo
    workflow.add_edge("tutor", END)
    workflow.add_edge("review", END)
    workflow.add_edge("quiz", END)
    workflow.add_edge("insight", END)

    return workflow.compile()
