"use client"

export function NuraLogo({ size = "default" }: { size?: "default" | "large" }) {
  const scale = size === "large" ? 1.5 : 1
  
  return (
    <div className="inline-flex flex-col items-start">
      {/* N + Constellation row */}
      <div className="flex items-center">
        <span 
          className="font-bold text-[#60a0ff]"
          style={{ fontSize: `${2.2 * scale}rem`, lineHeight: 1 }}
        >
          N
        </span>
        {/* Constellation dots - to the right of N */}
        <svg
          width={32 * scale}
          height={28 * scale}
          viewBox="0 0 32 28"
          fill="none"
          className="ml-1"
        >
          {/* Connection lines - thin */}
          <line x1="4" y1="14" x2="12" y2="8" stroke="#6c7086" strokeWidth="0.7" />
          <line x1="12" y1="8" x2="22" y2="12" stroke="#6c7086" strokeWidth="0.7" />
          <line x1="22" y1="12" x2="28" y2="6" stroke="#6c7086" strokeWidth="0.7" />
          <line x1="12" y1="8" x2="16" y2="20" stroke="#6c7086" strokeWidth="0.7" />
          <line x1="22" y1="12" x2="16" y2="20" stroke="#6c7086" strokeWidth="0.7" />
          {/* Colorful dots: yellow, purple, green, teal, pink */}
          <circle cx="4" cy="14" r="2.5" fill="#f9e2af" />
          <circle cx="12" cy="8" r="3" fill="#cba6f7" />
          <circle cx="22" cy="12" r="2.5" fill="#a6e3a1" />
          <circle cx="28" cy="6" r="2" fill="#74c7ec" />
          <circle cx="16" cy="20" r="2.5" fill="#f38ba8" />
        </svg>
      </div>
      {/* Nura text below */}
      <span 
        className="font-medium text-foreground"
        style={{ fontSize: `${1 * scale}rem`, marginTop: "-2px" }}
      >
        Nura
      </span>
      {/* Subtitle */}
      <span 
        className="text-muted-foreground"
        style={{ 
          fontSize: `${0.6 * scale}rem`, 
          letterSpacing: "0.1em",
          marginTop: "2px"
        }}
      >
        aprende · conecta · domina
      </span>
    </div>
  )
}
