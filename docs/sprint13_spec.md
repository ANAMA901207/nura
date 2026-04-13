# Sprint 13 — Bugs visuales y nombres

## Objetivo
Limpiar todos los elementos visuales inconsistentes
y establecer la nomenclatura definitiva de Nura.

## Cambios requeridos

### 1. Íconos SVG consistentes
- Eliminar todos los emojis de la UI (cerebro 🧠, quiz 🧩, 
  repaso 🔁, libro 📚, etc.)
- Reemplazar por íconos SVG Lucide coherentes en todas 
  las vistas: app.py, components.py, auth.py

### 2. Texto SM-2 amigable
- Reemplazar "SM-2 ha programado X concepto(s) para hoy"
  por texto natural: "Tienes X concepto(s) listos para repasar"

### 3. Botones Repasar/Flashcards prominentes
- Mover botones "Repasar ahora" y "Flashcards" a una 
  posición más visible — arriba de la sección, no escondidos

### 4. Nombres de navegación
- Chat → Descubrir
- Aprendizaje → Dominar  
- Mapa → Conectar
- Actualizar en sidebar, tabs, títulos y cualquier 
  referencia en el código

## Harness
- Ningún emoji visible en la UI (excepto streak 🔥)
- Texto SM-2 no aparece en ninguna vista
- Botones de repaso visibles sin hacer scroll
- Nombres Descubrir/Dominar/Conectar en toda la app