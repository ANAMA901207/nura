# Sprint 17 — Diagramas SVG automáticos en respuestas

## Objetivo
Cuando el tutor explica un concepto, generar automáticamente
un diagrama visual SVG que acompañe la explicación.

## Cuándo generar diagrama
- Respuestas del tutor sobre conceptos técnicos
- Cuando la explicación incluye flujos, jerarquías o relaciones
- Cuando el usuario pide "muéstrame", "diagrama", "esquema"

## Tipos de diagrama
1. Flujo lineal: A → B → C → D
2. Jerarquía: nodo padre con hijos
3. Comparación: dos columnas A vs B
4. Ciclo: pasos que se repiten

## Generación
- Gemini decide si el concepto necesita diagrama (bool)
- Si sí, Gemini genera descripción estructurada del diagrama
- Python construye el SVG con los colores de Nura
- Se renderiza debajo de la respuesta del tutor

## Estilo visual
- Colores de Nura: #60a0ff, #cba6f7, #a6e3a1, #f9e2af
- Fondo: #1e1e2e
- Tipografía: sans-serif, #cdd6f4
- Bordes redondeados, líneas con flechas

## Harness
- Gemini detecta correctamente si necesita diagrama
- SVG generado es válido (no vacío, tiene viewBox)
- Diagrama de flujo tiene al menos 2 nodos
- Fallo de generación no rompe la respuesta del tutor
- SVG se renderiza correctamente en Streamlit