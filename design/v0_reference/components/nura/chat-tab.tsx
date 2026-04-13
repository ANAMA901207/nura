"use client"

import { useState } from "react"
import { Brain, ChevronDown, ChevronUp, Search, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

export function ChatTab() {
  const [showFlashcard, setShowFlashcard] = useState(false)
  const [query, setQuery] = useState("")
  const [context, setContext] = useState("")
  const [showResult, setShowResult] = useState(true)

  return (
    <div className="flex flex-col gap-6">
      {/* Smart Insight Banner */}
      <div className="flex items-start gap-3 p-4 rounded-lg bg-card border-l-4 border-l-primary">
        <Brain className="w-6 h-6 text-primary flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-foreground">
            <span className="font-semibold">¡Buen progreso, María!</span> Has dominado el 78% de los conceptos de Química Orgánica. Te sugiero repasar alcanos y alquenos hoy.
          </p>
        </div>
      </div>

      {/* Search Input */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Escribe un término o pregunta..."
            className="pl-12 py-6 text-base bg-card border-border"
          />
        </div>
        <Input
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Contexto opcional"
          className="py-4 bg-card border-border text-muted-foreground"
        />
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <Button className="flex-1 gap-2 bg-primary text-primary-foreground hover:bg-primary/90">
          <Sparkles className="w-4 h-4" />
          Sesión de repaso
        </Button>
        <Button variant="outline" className="flex-1 gap-2 border-primary text-primary hover:bg-primary/10">
          Quiz
        </Button>
      </div>

      {/* Concept Card Result */}
      {showResult && (
        <div className="p-6 rounded-xl bg-card border border-border">
          <h3 className="text-xl font-bold text-foreground mb-3">Enlace Covalente</h3>
          
          {/* Category Badges */}
          <div className="flex gap-2 mb-4">
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-primary/20 text-primary">
              Química
            </span>
            <span className="px-3 py-1 rounded-full text-xs font-medium bg-secondary/20 text-secondary">
              Enlace Químico
            </span>
          </div>

          {/* Explanation */}
          <p className="text-foreground mb-4 leading-relaxed">
            Un enlace covalente es un tipo de enlace químico donde dos átomos comparten uno o más pares de electrones. 
            Este compartir permite que ambos átomos alcancen una configuración electrónica estable.
          </p>

          {/* Analogy */}
          <p className="text-muted-foreground italic mb-4">
            &quot;Imagina dos personas que comparten un paraguas bajo la lluvia — ambas se benefician del mismo recurso compartido.&quot;
          </p>

          {/* Expandable Flashcard */}
          <button
            onClick={() => setShowFlashcard(!showFlashcard)}
            className="flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
          >
            {showFlashcard ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            Ver flashcard
          </button>

          {showFlashcard && (
            <div className={cn(
              "mt-4 p-4 rounded-lg bg-muted border border-border",
              "animate-in fade-in-0 slide-in-from-top-2 duration-200"
            )}>
              <div className="text-center">
                <p className="text-xs uppercase tracking-wide text-muted-foreground mb-2">FRENTE</p>
                <p className="text-lg font-medium text-foreground">¿Qué es un enlace covalente?</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
