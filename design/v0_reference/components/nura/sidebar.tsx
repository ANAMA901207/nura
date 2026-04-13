"use client"

import { MessageSquare, BookOpen, Map, LogOut, Flame } from "lucide-react"
import { NuraLogo } from "./nura-logo"
import { cn } from "@/lib/utils"

interface SidebarProps {
  activeTab: "chat" | "aprendizaje" | "mapa"
  onTabChange: (tab: "chat" | "aprendizaje" | "mapa") => void
}

const navItems = [
  { id: "chat" as const, label: "Chat", icon: MessageSquare },
  { id: "aprendizaje" as const, label: "Aprendizaje", icon: BookOpen },
  { id: "mapa" as const, label: "Mapa", icon: Map },
]

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="flex flex-col h-full w-64 bg-sidebar border-r border-sidebar-border p-4">
      {/* Logo */}
      <div className="mb-8">
        <NuraLogo />
      </div>

      {/* User Profile */}
      <div className="flex items-center gap-3 mb-8 p-3 rounded-lg bg-muted">
        <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center">
          <span className="text-sm font-semibold text-primary-foreground">MR</span>
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">María Rodríguez</p>
          <p className="text-xs text-muted-foreground">Nurian</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeTab === item.id
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
            >
              <Icon className="w-5 h-5" />
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Daily Streak */}
      <div className="mt-auto pt-4 border-t border-sidebar-border">
        <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-muted">
          <Flame className="w-5 h-5 text-orange-400" />
          <span className="text-sm font-medium text-foreground">5 días seguidos</span>
        </div>
      </div>

      {/* Logout */}
      <button className="flex items-center gap-3 px-4 py-3 mt-4 rounded-lg text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
        <LogOut className="w-5 h-5" />
        Cerrar sesión
      </button>
    </aside>
  )
}
