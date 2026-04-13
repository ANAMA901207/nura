# Sprint 5 — Mejoras de clasificación

## Objetivo
Reducir errores de clasificación por términos ambiguos.

## Funcionalidades
1. Campo de contexto opcional en el chat
2. Botón "Corregir clasificación" en cada tarjeta
3. Actualización de todos los archivos afectados

## Harness
- Clasificador recibe y usa el contexto cuando se provee
- Corrección manual persiste en BD correctamente
- Campo contexto vacío no rompe el flujo existente
- Tarjeta muestra botón de corrección funcional

## Bug fix — conceptos vacíos por fallo de API
- Si el clasificador falla (timeout, cuota, error), 
  NO guardar el concepto en BD
- O si ya se guardó vacío, marcarlo como "pendiente de clasificar"
- Al reintentar el mismo término, si existe pero está vacío,
  reclasificar en lugar de lanzar error "ya existe"
- En la tabla de conceptos, mostrar badge "⚠️ Sin clasificar" 
  en lugar de mostrar campos vacíos