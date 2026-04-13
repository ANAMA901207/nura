# Sprint 17 Close — Diagramas SVG automáticos en respuestas del tutor

## Objetivo
Generar diagramas SVG visuales automáticamente al final de las respuestas del tutor cuando el contenido lo amerite, integrándolos en la vista Descubrir con el tema visual de Nura.

## Archivos creados
| Archivo | Descripción |
|---|---|
| `tools/diagram_tool.py` | Dos funciones públicas: `should_generate_diagram` y `generate_diagram_svg`. Incluye layout circular, constructor SVG y helpers de escaping. |
| `tests/test_sprint17.py` | 21 tests distribuidos en 5 clases (should_generate, generate_svg, API failure, tutor_agent integration, render_diagram). |

## Archivos modificados
| Archivo | Cambio |
|---|---|
| `agents/state.py` | Campo `diagram_svg: str` añadido a `NuraState` con docstring. |
| `agents/tutor_agent.py` | Paso 5 post-respuesta: llama a `should_generate_diagram` → `generate_diagram_svg`, guarda en `state["diagram_svg"]`. Envuelto en `try/except`. |
| `ui/components.py` | Función `render_diagram(svg_html)` que muestra el SVG en contenedor con borde `#45475a`. |
| `ui/app.py` | Import de `render_diagram`; llamada en el bloque `else` de respuesta del tutor (modo `question`) después de `render_sources`. |

## Implementación destacada

### `tools/diagram_tool.py`
- `should_generate_diagram`: prompt Gemini con JSON `{needs_diagram, diagram_type, reason}`. Devuelve `False` (sin excepción) en cualquier fallo.
- `generate_diagram_svg`: prompt Gemini con JSON `{nodes[], edges[], title}`. Construye SVG con viewBox="0 0 600 300", fondo `#1e1e2e`, nodos como rectángulos redondeados con paleta Nura, flechas con marcadores `<marker>`, texto `#cdd6f4`. Máximo 6 nodos con layout elíptico automático.
- Seguridad: los textos de nodos y aristas se escapan con `&lt;`/`&gt;` para prevenir inyección HTML.

### `agents/tutor_agent.py`
El paso 5 (nuevo) se ejecuta solo para `mode='question'` y fuera del bloque `try/except` principal, de modo que un fallo del diagram tool nunca afecta la respuesta del tutor. El resultado `diagram_svg` siempre se incluye en el dict de retorno (vacío o con SVG).

## Resultado del harness
```
181 passed, 17 warnings in 167.11s (0:02:47)
```
21 tests nuevos de Sprint 17. 0 regresiones.
