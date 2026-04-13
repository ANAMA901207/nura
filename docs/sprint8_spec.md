# Sprint 8 — Spaced Repetition SM-2

## Objetivo
Implementar el algoritmo SM-2 para sugerir repasos
en el momento óptimo de cada concepto.

## Algoritmo SM-2
- Cada concepto tiene un intervalo (días) y un factor de facilidad (EF)
- EF inicial = 2.5
- Después de cada repaso:
  - Si correcto: intervalo *= EF, EF aumenta levemente
  - Si incorrecto: intervalo = 1, EF disminuye
- next_review = hoy + intervalo

## Funcionalidades
1. SM-2 reemplaza la lógica simple de next_review del Sprint 7
2. Tab 2 muestra sección "Para repasar hoy" con conceptos 
   cuyo next_review <= hoy
3. Badge en Tab 2 con número de conceptos pendientes de repaso
4. Review agent usa SM-2 para sugerir repasos

## Harness
- EF se actualiza correctamente tras acierto y error
- Intervalo crece exponencialmente con aciertos consecutivos
- Concepto con next_review=hoy aparece en "Para repasar hoy"
- Concepto con next_review=mañana no aparece
- Error resetea intervalo a 1