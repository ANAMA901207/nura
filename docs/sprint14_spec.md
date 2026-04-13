# Sprint 14 — UX e Interacción

## Objetivo
Mejorar la experiencia de interacción con Nura — 
detección de ambigüedad, edición de conceptos, 
filtro de mapa y corrección ortográfica.

## Funcionalidades

### 1. Detección de ambigüedad
- Antes de clasificar, detectar si el término tiene 
  múltiples significados posibles (cursor, python, mercury...)
- Si es ambiguo, Nura pregunta: "¿Te refieres a X o a Y?"
- Usuario elige y luego clasifica con el contexto correcto

### 2. Editar y eliminar conceptos
- En "Mis conceptos", botón "Editar" por cada concepto
- Permite modificar: term, category, explanation
- Botón "Eliminar" con confirmación antes de borrar
- Operaciones reflejadas inmediatamente en el mapa

### 3. Filtro mapa — Explorar concepto
- Al seleccionar un concepto en "Explorar concepto"
  el mapa filtra y muestra SOLO ese nodo y sus conexiones
- Botón "Ver todo" para restaurar el mapa completo

### 4. Corrección ortográfica
- Antes de capturar, verificar si el término parece 
  tener error ortográfico
- Si sí, preguntar: "¿Quisiste decir EBITDA?" 
  antes de guardarlo
- Usuario confirma o escribe el término correcto

## Harness
- Término ambiguo activa modo de clarificación
- Editar concepto persiste cambios en BD
- Eliminar concepto lo remueve de BD y del mapa
- Filtro de mapa muestra solo nodo seleccionado y conexiones
- Término con typo activa sugerencia de corrección