"use client"

import { useState } from "react"
import { BookOpen, Link2, RefreshCw, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

const metrics = [
  { label: "Conceptos capturados", value: 47, icon: BookOpen, color: "text-primary" },
  { label: "Conexiones nuevas", value: 12, icon: Link2, color: "text-secondary" },
  { label: "Repasados hoy", value: 8, icon: RefreshCw, color: "text-[#a6e3a1]" },
]

const categories = [
  { name: "Química Orgánica", progress: 78, color: "bg-primary" },
  { name: "Biología Celular", progress: 62, color: "bg-secondary" },
  { name: "Física Mecánica", progress: 45, color: "bg-[#cba6f7]" },
  { name: "Matemáticas", progress: 85, color: "bg-[#a6e3a1]" },
]

const flashcards = [
  { front: "¿Qué es la mitosis?", back: "División celular que produce dos células hijas idénticas a la célula madre." },
  { front: "¿Qué es un enlace covalente?", back: "Un enlace donde dos átomos comparten electrones." },
  { front: "¿Cuál es la fórmula de la velocidad?", back: "v = d/t (velocidad = distancia / tiempo)" },
]

export function AprendizajeTab() {
  const [currentCard, setCurrentCard] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)

  const handleNext = () => {
    setIsFlipped(false)
    setCurrentCard((prev) => (prev + 1) % flashcards.length)
  }

  const handleFlip = () => {
    setIsFlipped(!isFlipped)
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Metric Cards */}
      <div className="grid grid-cols-3 gap-4">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <div
              key={metric.label}
              className="p-5 rounded-xl bg-card border border-border"
            >
              <div className="flex items-center gap-3 mb-2">
                <Icon className={`w-5 h-5 ${metric.color}`} />
                <span className="text-2xl font-bold text-foreground">{metric.value}</span>
              </div>
              <p className="text-sm text-muted-foreground">{metric.label}</p>
            </div>
          )
        })}
      </div>

      {/* Flashcard */}
      <div className="p-8 rounded-xl bg-card border border-border min-h-[240px] flex flex-col">
        <p className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
          {isFlipped ? "REVERSO" : "FRENTE"}
        </p>
        <p className="text-sm text-muted-foreground mb-6">
          Tarjeta {currentCard + 1} de {flashcards.length}
        </p>
        
        <div className="flex-1 flex items-center justify-center">
          <p className="text-xl font-medium text-foreground text-center">
            {isFlipped ? flashcards[currentCard].back : flashcards[currentCard].front}
          </p>
        </div>

        <div className="flex gap-3 mt-6">
          <Button
            onClick={handleFlip}
            variant="outline"
            className="flex-1 border-primary text-primary hover:bg-primary/10"
          >
            Voltear
          </Button>
          <Button
            onClick={handleNext}
            className="flex-1 gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
          >
            Siguiente
            <ArrowRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Progress by Category */}
      <div className="p-6 rounded-xl bg-card border border-border">
        <h3 className="text-lg font-semibold text-foreground mb-5">Progreso por categoría</h3>
        <div className="space-y-4">
          {categories.map((category) => (
            <div key={category.name}>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-foreground">{category.name}</span>
                <span className="text-sm text-muted-foreground">{category.progress}%</span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full ${category.color} transition-all duration-500`}
                  style={{ width: `${category.progress}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
