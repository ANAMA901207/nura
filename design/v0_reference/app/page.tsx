"use client"

import { useState } from "react"
import { Sidebar } from "@/components/nura/sidebar"
import { ChatTab } from "@/components/nura/chat-tab"
import { AprendizajeTab } from "@/components/nura/aprendizaje-tab"
import { MapaTab } from "@/components/nura/mapa-tab"

export default function NuraApp() {
  const [activeTab, setActiveTab] = useState<"chat" | "aprendizaje" | "mapa">("chat")

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content */}
      <main className="flex-1 overflow-auto p-8">
        <div className="max-w-4xl mx-auto">
          {/* Page Title */}
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground mb-1">
              {activeTab === "chat" && "Chat Inteligente"}
              {activeTab === "aprendizaje" && "Mi Aprendizaje"}
              {activeTab === "mapa" && "Mapa de Conocimiento"}
            </h1>
            <p className="text-muted-foreground">
              {activeTab === "chat" && "Pregunta, aprende y conecta conceptos"}
              {activeTab === "aprendizaje" && "Tu progreso y flashcards de repaso"}
              {activeTab === "mapa" && "Visualiza las conexiones entre conceptos"}
            </p>
          </div>

          {/* Tab Content */}
          {activeTab === "chat" && <ChatTab />}
          {activeTab === "aprendizaje" && <AprendizajeTab />}
          {activeTab === "mapa" && <MapaTab />}
        </div>
      </main>
    </div>
  )
}
