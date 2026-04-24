# Sprint 23 — Fix sesión que expira

## Objetivo
Que el usuario no sea expulsado de Nura por inactividad.
La sesión debe persistir mientras el browser esté abierto.

## Problema actual
El token de Supabase expira y Streamlit no lo renueva
automáticamente. El usuario se loguea, deja la app un rato,
vuelve y está botado — tiene que registrarse de nuevo.

## Causa raíz probable
`st.session_state` pierde el token cuando Streamlit hace rerun
o cuando el token de Supabase expira (por defecto 1 hora).

## Solución
1. Guardar el token y user_id en `st.session_state` al login
2. Al inicio de cada rerun, verificar si hay sesión activa
   y refrescarla automáticamente con Supabase
3. Solo pedir login si no hay sesión válida recuperable

## Archivos a modificar
- `ui/auth.py` — lógica de login, logout y refresh de sesión
- `ui/app.py` — verificación de sesión al inicio de cada rerun

## Comportamiento esperado
- Usuario se loguea → sesión persiste aunque no interactúe
- Si el token expiró → se refresca silenciosamente sin botar
- Solo se pide login si el usuario cerró sesión explícitamente
  o si el refresh falla

## Harness
- Sesión persiste después de simular rerun de Streamlit
- Token expirado se refresca sin mostrar pantalla de login
- Logout explícito sí limpia la sesión correctamente
- Usuario sin sesión ve pantalla de login

## Reglas
- No romper el flujo de auth existente (bcrypt, onboarding)
- No tocar agentes ni BD
- Preservar todos los tests existentes en verde