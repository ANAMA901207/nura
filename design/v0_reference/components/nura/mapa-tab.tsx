"use client"

import { useState } from "react"

interface Node {
  id: string
  label: string
  x: number
  y: number
  category: "chemistry" | "biology" | "physics" | "math"
  connections: string[]
}

const nodes: Node[] = [
  { id: "1", label: "Enlace Químico", x: 50, y: 25, category: "chemistry", connections: ["2", "3"] },
  { id: "2", label: "Covalente", x: 22, y: 45, category: "chemistry", connections: ["1", "4"] },
  { id: "3", label: "Iónico", x: 78, y: 42, category: "chemistry", connections: ["1", "5"] },
  { id: "4", label: "Molécula", x: 12, y: 72, category: "biology", connections: ["2", "6"] },
  { id: "5", label: "Electrón", x: 88, y: 68, category: "physics", connections: ["3", "6"] },
  { id: "6", label: "Átomo", x: 50, y: 78, category: "physics", connections: ["4", "5"] },
  { id: "7", label: "Energía", x: 35, y: 60, category: "physics", connections: ["2", "6"] },
  { id: "8", label: "Fórmula", x: 65, y: 58, category: "math", connections: ["3", "6"] },
]

const categoryColors = {
  chemistry: "#60a0ff",
  biology: "#74c7ec",
  physics: "#cba6f7",
  math: "#a6e3a1",
}

const categoryLabels = {
  chemistry: "Química",
  biology: "Biología",
  physics: "Física",
  math: "Matemáticas",
}

export function MapaTab() {
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-foreground mb-2">Mapa de Conocimiento</h2>
        <p className="text-muted-foreground">
          Visualiza las conexiones entre los conceptos que has aprendido.
        </p>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4">
        {Object.entries(categoryLabels).map(([key, label]) => (
          <div key={key} className="flex items-center gap-2">
            <div 
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: categoryColors[key as keyof typeof categoryColors] }}
            />
            <span className="text-sm text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>

      {/* Knowledge Map - Constellation Style */}
      <div className="relative h-[450px] rounded-xl bg-card border border-border overflow-hidden">
        <svg className="absolute inset-0 w-full h-full">
          {/* Connection Lines - thin, organic */}
          {nodes.flatMap((node) =>
            node.connections.map((targetId) => {
              const target = nodes.find((n) => n.id === targetId)
              if (!target || node.id > targetId) return null
              const isHighlighted = selectedNode === node.id || selectedNode === targetId
              return (
                <line
                  key={`${node.id}-${targetId}`}
                  x1={`${node.x}%`}
                  y1={`${node.y}%`}
                  x2={`${target.x}%`}
                  y2={`${target.y}%`}
                  stroke={isHighlighted ? "#60a0ff" : "#45475a"}
                  strokeWidth={isHighlighted ? 2 : 1}
                  opacity={isHighlighted ? 1 : 0.5}
                  className="transition-all duration-300"
                />
              )
            })
          )}
          
          {/* Circle Nodes */}
          {nodes.map((node) => {
            const isSelected = selectedNode === node.id
            const color = categoryColors[node.category]
            const radius = isSelected ? 42 : 38
            
            return (
              <g 
                key={node.id} 
                className="cursor-pointer transition-all duration-200"
                onClick={() => setSelectedNode(selectedNode === node.id ? null : node.id)}
              >
                {/* Glow effect for selected */}
                {isSelected && (
                  <circle
                    cx={`${node.x}%`}
                    cy={`${node.y}%`}
                    r={radius + 6}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    opacity="0.4"
                  />
                )}
                {/* Main circle */}
                <circle
                  cx={`${node.x}%`}
                  cy={`${node.y}%`}
                  r={radius}
                  fill={color}
                  className="hover:opacity-90 transition-opacity"
                />
                {/* Label */}
                <text
                  x={`${node.x}%`}
                  y={`${node.y}%`}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="#1e1e2e"
                  fontSize="11"
                  fontWeight="600"
                  className="pointer-events-none select-none"
                >
                  {node.label}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      {/* Selected Node Details */}
      {selectedNode && (
        <div className="p-4 rounded-lg bg-card border border-border animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
          <h3 className="font-semibold text-foreground mb-2">
            {nodes.find((n) => n.id === selectedNode)?.label}
          </h3>
          <p className="text-sm text-muted-foreground">
            Conectado con: {nodes
              .find((n) => n.id === selectedNode)
              ?.connections.map((c) => nodes.find((n) => n.id === c)?.label)
              .join(", ")}
          </p>
        </div>
      )}
    </div>
  )
}
