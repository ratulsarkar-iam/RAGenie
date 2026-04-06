interface GenieLogoProps {
  className?: string
  size?: number
}

export default function GenieLogo({ className = '', size = 40 }: GenieLogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      <defs>
        <linearGradient id="logoGrad" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#6366F1" />
          <stop offset="50%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
        <linearGradient id="lampGrad" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#8B5CF6" />
          <stop offset="100%" stopColor="#6366F1" />
        </linearGradient>
        <linearGradient id="smokeGrad" x1="50%" y1="100%" x2="50%" y2="0%">
          <stop offset="0%" stopColor="#8B5CF6" />
          <stop offset="40%" stopColor="#A78BFA" />
          <stop offset="100%" stopColor="#06B6D4" />
        </linearGradient>
        <linearGradient id="nodeGrad" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#A78BFA" />
          <stop offset="100%" stopColor="#22D3EE" />
        </linearGradient>
        <radialGradient id="glowCenter" cx="50%" cy="30%" r="50%">
          <stop offset="0%" stopColor="#C4B5FD" stopOpacity="0.3" />
          <stop offset="100%" stopColor="transparent" stopOpacity="0" />
        </radialGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="1.5" result="coloredBlur"/>
          <feMerge>
            <feMergeNode in="coloredBlur"/>
            <feMergeNode in="SourceGraphic"/>
          </feMerge>
        </filter>
      </defs>

      {/* Subtle background glow */}
      <circle cx="50" cy="40" r="38" fill="url(#glowCenter)" />

      {/* Sleek minimal lamp base */}
      <path
        d="M38 90 L62 90 Q63 88 62 86 L38 86 Q37 88 38 90 Z"
        fill="url(#lampGrad)"
        opacity="0.9"
      />

      {/* Lamp body — elegant curved vessel */}
      <path
        d="M40 86 L38 80 Q36 74 40 70 L46 66 Q50 64 54 66 L60 70 Q64 74 62 80 L60 86 Z"
        fill="url(#lampGrad)"
      />

      {/* Lamp highlight */}
      <path
        d="M43 83 L42 78 Q41 75 43 72 L47 69 Q49 68 50 68"
        stroke="white"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.3"
        fill="none"
      />

      {/* Lamp spout */}
      <path
        d="M36 74 Q32 72 28 74 Q30 71 34 71 Q36 71 38 73"
        fill="url(#lampGrad)"
      />

      {/* Rising smoke / knowledge stream — elegant S-curve */}
      <path
        d="M30 72 Q26 60 36 50 Q46 40 40 28 Q36 22 42 14"
        stroke="url(#smokeGrad)"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
        opacity="0.6"
      />
      <path
        d="M30 72 Q24 58 38 46 Q50 36 42 22 Q38 16 44 10"
        stroke="url(#smokeGrad)"
        strokeWidth="1.5"
        strokeLinecap="round"
        fill="none"
        opacity="0.3"
      />

      {/* Knowledge nodes — constellation pattern */}
      <g filter="url(#glow)">
        {/* Primary nodes */}
        <circle cx="36" cy="50" r="3.5" fill="url(#nodeGrad)" />
        <circle cx="42" cy="34" r="4" fill="url(#nodeGrad)" />
        <circle cx="30" cy="62" r="3" fill="url(#nodeGrad)" />

        {/* Secondary nodes */}
        <circle cx="55" cy="28" r="3" fill="url(#nodeGrad)" />
        <circle cx="28" cy="42" r="2.5" fill="url(#nodeGrad)" />
        <circle cx="50" cy="46" r="2.5" fill="url(#nodeGrad)" />

        {/* Tertiary nodes */}
        <circle cx="44" cy="14" r="2" fill="#22D3EE" />
        <circle cx="60" cy="40" r="2" fill="url(#nodeGrad)" opacity="0.7" />
        <circle cx="22" cy="54" r="1.5" fill="url(#nodeGrad)" opacity="0.5" />
      </g>

      {/* Connection lines between nodes */}
      <g stroke="url(#nodeGrad)" strokeWidth="1" opacity="0.4">
        <line x1="30" y1="62" x2="36" y2="50" />
        <line x1="36" y1="50" x2="42" y2="34" />
        <line x1="42" y1="34" x2="55" y2="28" />
        <line x1="36" y1="50" x2="50" y2="46" />
        <line x1="50" y1="46" x2="60" y2="40" />
        <line x1="42" y1="34" x2="28" y2="42" />
        <line x1="28" y1="42" x2="22" y2="54" />
        <line x1="42" y1="34" x2="44" y2="14" />
        <line x1="55" y1="28" x2="60" y2="40" />
      </g>

      {/* Top sparkle — the "magic" moment */}
      <g filter="url(#glow)">
        <path
          d="M44 8 L45.5 11 L49 12 L46 13.5 L46.5 17 L44 14.5 L41.5 17 L42 13.5 L39 12 L42.5 11 Z"
          fill="#22D3EE"
        />
      </g>

      {/* Accent sparkles */}
      <circle cx="62" cy="22" r="1.5" fill="#22D3EE" opacity="0.8" />
      <circle cx="68" cy="34" r="1" fill="#A78BFA" opacity="0.6" />
      <circle cx="18" cy="36" r="1" fill="#22D3EE" opacity="0.5" />

      {/* Document page icon inside the largest node */}
      <g opacity="0.9">
        <rect x="39" y="30" rx="1" ry="1" width="6" height="8" fill="white" opacity="0.8" />
        <line x1="40.5" y1="33" x2="43.5" y2="33" stroke="#6366F1" strokeWidth="0.7" />
        <line x1="40.5" y1="35" x2="43.5" y2="35" stroke="#6366F1" strokeWidth="0.7" />
      </g>
    </svg>
  )
}
