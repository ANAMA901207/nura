"""
tools/diagram_tool.py
=====================
Herramientas para generar diagramas SVG automáticos a partir de texto
explicativo del tutor de Nura.

Flujo de uso (Sprint 17)
------------------------
1. should_generate_diagram(text, profile) — pregunta a Gemini si el texto
   se beneficiaría de un diagrama y qué tipo sería el más adecuado.
2. generate_diagram_svg(text, diagram_type) — pide a Gemini la estructura
   del diagrama (nodos y aristas) y construye un SVG con el tema de Nura.

Diseño SVG
----------
- viewBox="0 0 600 300", fondo #1e1e2e.
- Nodos: rectángulos redondeados, paleta de colores de Nura:
  #60a0ff (azul), #cba6f7 (morado), #a6e3a1 (verde), #f9e2af (amarillo).
- Texto de nodos y título: #cdd6f4.
- Aristas: líneas con marcadores de flecha, color #6c7086.
- Si la llamada a Gemini falla, ambas funciones retornan valores seguros
  (False / cadena vacía) sin propagar la excepción.
"""

from __future__ import annotations

import json
import math
import os
import re

# ── Paleta de colores de Nura ─────────────────────────────────────────────────
_NODE_COLORS = ["#60a0ff", "#cba6f7", "#a6e3a1", "#f9e2af", "#f38ba8", "#89dceb"]
_BG_COLOR    = "#1e1e2e"
_EDGE_COLOR  = "#6c7086"
_TEXT_COLOR  = "#cdd6f4"


# ── LLM helpers ───────────────────────────────────────────────────────────────

def _call_gemini_json(prompt: str) -> dict:
    """
    Llama a Gemini esperando una respuesta JSON.

    Elimina bloques markdown del output antes de parsear.

    Parámetros
    ----------
    prompt : Prompt completo a enviar.

    Devuelve
    --------
    dict con la respuesta parseada.

    Lanza
    -----
    Exception si la llamada falla o el JSON es inválido.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    api_key    = os.environ.get("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,  # type: ignore[call-arg]
        temperature=0,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    text = str(response.content).strip()
    # Eliminar bloques ```json ... ```
    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(text)


# ── Construcción SVG ──────────────────────────────────────────────────────────

def _wrap_label(label: str, max_chars: int = 18) -> list[str]:
    """
    Divide un label largo en líneas de máximo max_chars caracteres.

    Intenta cortar en espacios para no partir palabras.
    Devuelve máximo 2 líneas.
    """
    label = label.strip()
    if len(label) <= max_chars:
        return [label]
    # Intentar cortar en el último espacio antes del límite
    cut = label.rfind(" ", 0, max_chars + 1)
    if cut <= 0:
        cut = max_chars
    line1 = label[:cut].strip()
    line2 = label[cut:].strip()
    # Truncar segunda línea si sigue siendo muy larga
    if len(line2) > max_chars:
        line2 = line2[: max_chars - 1] + "…"
    return [line1, line2]


def _layout_nodes(nodes: list[dict]) -> dict[str, tuple[float, float]]:
    """
    Calcula coordenadas (cx, cy) para cada nodo en un layout circular.

    Usa un SVG de 760×400.  Para pocos nodos (≤ 3) usa layout lineal horizontal
    para que no queden aplastados en el centro.

    Parámetros
    ----------
    nodes : Lista de dicts con al menos la clave 'id'.

    Devuelve
    --------
    dict[node_id → (cx, cy)] con las coordenadas de centro de cada nodo.
    """
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]["id"]: (380.0, 200.0)}

    W, H = 760.0, 400.0
    cx_center = W / 2
    cy_center = H / 2 + 5  # ligero desplazamiento hacia abajo por el título

    # Radios generosos para que los nodos respiren
    rx = min(W * 0.38, 280.0)
    ry = min(H * 0.36, 130.0)

    positions: dict[str, tuple[float, float]] = {}
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = cx_center + rx * math.cos(angle)
        y = cy_center + ry * math.sin(angle)
        positions[node["id"]] = (x, y)
    return positions


def _build_svg(nodes: list[dict], edges: list[dict], title: str) -> str:
    """
    Construye el SVG completo a partir de nodos, aristas y título.

    Dimensiones: 760×400.  Nodos más anchos (160×44), texto en dos líneas
    cuando el label es largo, etiquetas de aristas con fondo semitransparente
    para legibilidad.

    Parámetros
    ----------
    nodes  : Lista de dicts con 'id', 'label' y opcionalmente 'color'.
    edges  : Lista de dicts con 'from', 'to' y opcionalmente 'label'.
    title  : Texto del título del diagrama.

    Devuelve
    --------
    str con el SVG completo listo para embeber en HTML.
    """
    W, H = 760, 400
    positions = _layout_nodes(nodes)
    node_w, node_h = 160, 46

    def _esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px;">',
        f'<rect width="{W}" height="{H}" fill="{_BG_COLOR}" rx="12"/>',
        '<defs>',
        f'<marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">',
        f'  <path d="M0,0 L0,6 L9,3 z" fill="{_EDGE_COLOR}"/>',
        '</marker>',
        '</defs>',
    ]

    # Título
    if title:
        lines.append(
            f'<text x="{W//2}" y="28" text-anchor="middle" '
            f'font-family="system-ui,sans-serif" font-size="13" '
            f'font-weight="700" fill="{_TEXT_COLOR}">{_esc(title)}</text>'
        )

    # Aristas — debajo de los nodos
    id_set = set(positions.keys())
    for edge in edges:
        src, dst = edge.get("from", ""), edge.get("to", "")
        if src not in id_set or dst not in id_set:
            continue
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1
        # Acortar flecha para que apunte al borde del nodo destino
        margin = math.hypot(node_w / 2, node_h / 2) + 5
        ratio  = max(0.0, (dist - margin) / dist)
        # Punto de salida: desde el borde del nodo origen
        start_ratio = math.hypot(node_w / 2, node_h / 2) / dist
        sx = x1 + dx * min(start_ratio, 0.4)
        sy = y1 + dy * min(start_ratio, 0.4)
        ex, ey = x1 + dx * ratio, y1 + dy * ratio
        lines.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
            f'stroke="{_EDGE_COLOR}" stroke-width="1.5" marker-end="url(#arr)"/>'
        )
        # Etiqueta de arista con fondo semitransparente
        lbl = (edge.get("label") or "").strip()
        if lbl:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2 - 8
            safe_lbl = _esc(lbl[:28])
            lbl_w = min(len(lbl) * 6.5, 180)
            lines.append(
                f'<rect x="{mx - lbl_w/2:.1f}" y="{my - 11:.1f}" '
                f'width="{lbl_w:.0f}" height="14" rx="3" '
                f'fill="{_BG_COLOR}" fill-opacity="0.85"/>'
            )
            lines.append(
                f'<text x="{mx:.1f}" y="{my:.1f}" text-anchor="middle" '
                f'font-family="system-ui,sans-serif" font-size="9.5" '
                f'fill="{_EDGE_COLOR}">{safe_lbl}</text>'
            )

    # Nodos
    for idx, node in enumerate(nodes):
        nid   = node.get("id", f"n{idx}")
        label = (node.get("label") or nid).strip()
        color = node.get("color") or _NODE_COLORS[idx % len(_NODE_COLORS)]
        if nid not in positions:
            continue
        cx, cy = positions[nid]
        rx_n = cx - node_w / 2
        ry_n = cy - node_h / 2

        # Rectángulo del nodo con relleno suave y borde coloreado
        lines.append(
            f'<rect x="{rx_n:.1f}" y="{ry_n:.1f}" '
            f'width="{node_w}" height="{node_h}" rx="10" '
            f'fill="{color}1a" stroke="{color}" stroke-width="2"/>'
        )

        # Texto en 1 o 2 líneas
        lines_txt = _wrap_label(label, max_chars=19)
        if len(lines_txt) == 1:
            safe_l = _esc(lines_txt[0])
            lines.append(
                f'<text x="{cx:.1f}" y="{cy + 5:.1f}" text-anchor="middle" '
                f'font-family="system-ui,sans-serif" font-size="11.5" '
                f'font-weight="600" fill="{_TEXT_COLOR}">{safe_l}</text>'
            )
        else:
            l1, l2 = _esc(lines_txt[0]), _esc(lines_txt[1])
            lines.append(
                f'<text x="{cx:.1f}" y="{cy - 3:.1f}" text-anchor="middle" '
                f'font-family="system-ui,sans-serif" font-size="11" '
                f'font-weight="600" fill="{_TEXT_COLOR}">{l1}</text>'
            )
            lines.append(
                f'<text x="{cx:.1f}" y="{cy + 11:.1f}" text-anchor="middle" '
                f'font-family="system-ui,sans-serif" font-size="11" '
                f'font-weight="600" fill="{_TEXT_COLOR}">{l2}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


# ── Funciones públicas ────────────────────────────────────────────────────────

def should_generate_diagram(concept_text: str, user_profile: dict) -> bool:
    """
    Determina si el texto de respuesta del tutor se beneficiaría de un diagrama.

    Llama a Gemini con un prompt ligero de clasificación.  Si la llamada
    falla por cualquier motivo, retorna False para no bloquear el flujo.

    Parámetros
    ----------
    concept_text : Texto de la respuesta generada por tutor_agent.
    user_profile : Perfil del usuario (actualmente no usado en el prompt,
                   reservado para personalización futura).

    Devuelve
    --------
    bool — True si Gemini recomienda generar un diagrama.
    """
    if not concept_text or not concept_text.strip():
        return False

    # Usar solo las primeras 600 chars para mantener el prompt compacto
    snippet = concept_text.strip()[:600]
    prompt = (
        f'El siguiente texto de explicación se beneficiaría de un diagrama visual? '
        f'Texto: "{snippet}". '
        f'Responde SOLO con JSON válido: '
        f'{{"needs_diagram": true_o_false, '
        f'"diagram_type": "flow|hierarchy|comparison|cycle|none", '
        f'"reason": "motivo breve"}}'
    )
    try:
        result = _call_gemini_json(prompt)
        return bool(result.get("needs_diagram", False))
    except Exception:
        return False


def generate_diagram_svg(concept_text: str, diagram_type: str) -> str:
    """
    Genera un SVG con un diagrama del tipo indicado para el texto dado.

    Llama a Gemini para obtener la estructura del diagrama (nodos y aristas)
    y luego construye el SVG con el tema visual de Nura.  Si la llamada
    falla o la respuesta no tiene nodos válidos, retorna cadena vacía.

    Parámetros
    ----------
    concept_text : Texto que el diagrama debe ilustrar.
    diagram_type : Tipo de diagrama: 'flow', 'hierarchy', 'comparison',
                   'cycle' o 'none'.  Si es 'none', retorna vacío.

    Devuelve
    --------
    str — SVG completo listo para embeber en HTML, o cadena vacía si falla.
    """
    if not concept_text or diagram_type in ("none", ""):
        return ""

    snippet = concept_text.strip()[:600]
    prompt = (
        f'Genera la estructura de un diagrama {diagram_type} para explicar: '
        f'"{snippet}". '
        f'Responde SOLO con JSON válido con esta estructura exacta: '
        f'{{"nodes": [{{"id": "n1", "label": "Nombre corto", "color": "#60a0ff"}}], '
        f'"edges": [{{"from": "n1", "to": "n2", "label": "verbo corto"}}], '
        f'"title": "Título breve (max 6 palabras)"}}. '
        f'Reglas IMPORTANTES: '
        f'(1) Máximo 6 nodos. '
        f'(2) Cada label de nodo: máximo 4 palabras, conciso y claro. '
        f'(3) Cada label de arista: máximo 4 palabras (ej: "genera", "controla", "sube"). '
        f'(4) IDs: cadenas cortas sin espacios (ej: "banco", "tasa", "inflacion"). '
        f'(5) Colores de paleta: #60a0ff, #cba6f7, #a6e3a1, #f9e2af, #f38ba8, #89dceb.'
    )
    try:
        data  = _call_gemini_json(prompt)
        nodes = data.get("nodes") or []
        edges = data.get("edges") or []
        title = data.get("title") or ""

        if not nodes:
            return ""

        # Limitar a 6 nodos para que quepan en el viewBox
        nodes = nodes[:6]
        return _build_svg(nodes, edges, title)
    except Exception:
        return ""
