"""
agents/connector_agent.py
=========================
Tercer nodo del grafo: detecta y persiste conexiones semánticas entre el
concepto recién clasificado y los conceptos previos en la BD.

Llama a find_connections() con la lista de conceptos anteriores (excluye
el actual para evitar auto-conexiones), y persiste cada vínculo encontrado
con save_connection().  Actualiza new_connections en el estado con las
Connection creadas durante este ciclo.
"""

from __future__ import annotations

from db.models import Connection
from db.operations import save_connection
from agents.state import NuraState
from tools.connector_tool import find_connections

# Sprint 19: tools formales disponibles para bind_tools() en invocaciones
# externas y para registro en ToolNode del grafo.
try:
    from tools.db_tools import NURA_TOOLS as _NURA_TOOLS  # noqa: F401
except ImportError:
    _NURA_TOOLS = []


def connector_agent(state: NuraState) -> dict:
    """
    Nodo de conexión: encuentra y persiste vínculos semánticos con conceptos previos.

    Flujo interno
    -------------
    1. Recupera current_concept y all_concepts del estado.
    2. Filtra all_concepts para excluir el concepto actual (no conectar consigo mismo).
    3. Si no hay conceptos previos, devuelve new_connections=[] sin llamar a la API
       (find_connections hace el cortocircuito internamente, pero también se verifica aquí).
    4. Llama a find_connections(current_concept, other_concepts) → list[dict].
    5. Por cada dict {concept_id, relationship} llama a save_connection() para persistir.
    6. Errores individuales de save_connection se omiten silenciosamente para no
       abortar el nodo entero por una sola conexión inválida.

    Parámetros
    ----------
    state : Estado actual del grafo.  Requiere current_concept != None.

    Devuelve
    --------
    dict parcial con new_connections (lista de Connection) y response actualizados.

    Lanza
    -----
    ValueError : Si current_concept es None.
    """
    concept = state.get("current_concept")
    if concept is None:
        raise ValueError(
            "connector_agent requiere current_concept en el estado. "
            "Verifica que capture_agent y classifier_agent se ejecutaron antes."
        )

    user_id: int = state.get("user_id", 1)  # Sprint 11

    # Excluye el concepto actual para evitar que el modelo lo conecte consigo mismo
    other_concepts = [c for c in state.get("all_concepts", []) if c.id != concept.id]

    # find_connections devuelve [] de inmediato si other_concepts está vacío
    connections_data = find_connections(concept, other_concepts)

    saved_connections: list[Connection] = []
    for item in connections_data:
        try:
            conn = save_connection(
                concept_id_a=concept.id,
                concept_id_b=item["concept_id"],
                relationship=item["relationship"],
                user_id=user_id,
            )
            saved_connections.append(conn)
        except ValueError:
            # Si el ID ya no existe en la BD u otro error de negocio, se omite
            # esa conexión individual en lugar de abortar todo el nodo.
            pass

    n = len(saved_connections)
    response = (
        f"Se encontraron {n} conexion(es) para '{concept.term}'."
        if n > 0
        else f"No se encontraron conexiones para '{concept.term}'."
    )

    return {
        "new_connections": saved_connections,
        "response": response,
    }
