# Sprint 22 — Migración a Supabase

## Objetivo
Migrar la BD de SQLite local a Supabase (PostgreSQL)
para que Nura funcione desde cualquier dispositivo.

## Cambios
1. Instalar psycopg2 para conectar con PostgreSQL
2. Modificar db/schema.py para usar PostgreSQL
3. Modificar db/operations.py para usar PostgreSQL
4. Mantener compatibilidad con SQLite para tests locales
5. Variable DATABASE_URL en .env controla qué BD usar

## Estrategia
- Si DATABASE_URL existe en .env → usar Supabase
- Si no existe → usar SQLite local (para tests)
- Misma interfaz de operaciones para ambos

## Harness
- Tests siguen pasando con SQLite
- Conexión a Supabase funciona correctamente
- Tablas se crean en Supabase automáticamente
- CRUD operations funcionan en PostgreSQL